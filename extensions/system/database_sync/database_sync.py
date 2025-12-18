"""
TimescaleDB Database Synchronization
"""
import logging
import math
import threading
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, Dict, List, Set, Sequence, Iterable

import environ
import numpy as np
import psycopg
from psycopg import sql
from databeam_mcap_reader import Collector

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.data_interface.module_meta_factory import ModuleMetaFactory
from vif.data_interface.network_messages import Status, MeasurementStateType, StartStopCmd

from system.database_sync.config import DatabaseSyncConfig

logging.getLogger('databeam_mcap').setLevel(logging.WARNING)  # or other logging level


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='DatabaseSync')


class DatabaseSync(IOModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME

        self.data_broker.capabilities.capture_data = False
        self.data_broker.capabilities.live_data = False

        # worker thread starting and stopping is locked to avoid race condition during apply config vs. prepare sampling
        self._thread_handling_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        # worker thread stops when this event is set
        self._thread_stop_event = threading.Event()

        # sync all timestamps if true
        self._force_resync = False
        self._sync_start_ev = threading.Event()
        self._sync_stop_ev = threading.Event()

    def start(self):
        self.logger.debug('starting')

    def stop(self):
        self._stop_thread()
        self.logger.info('module closed')

    def _try_database_connection(self, dsn: str):
        # Try to connect to the target database
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            with conn.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
                cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb_toolkit;")
        self.logger.info("Successfully connected to DB and ensured extensions.")
        # raises on error

    @staticmethod
    def _safe_table_name(topic: str) -> str:
        base = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in topic.strip().lower())
        if not base or base[0].isdigit():
            base = f"t_{base}"
        return f"{base}"

    def _get_table_name_from_topic_module(self, module: str, topic_name: str) -> str:
        if topic_name == module:
            return self._safe_table_name(topic_name)
        else:
            return self._safe_table_name(f"{module}_{topic_name}")

    def _create_update_table(self, conn, table_name: str, channels: Set[str]):
        self.logger.info('_create_update_table: table "%s", channels %s', table_name, channels)

        with conn.cursor() as cur:
            # create table if not exists with time column
            # note: PRIMARY KEY (time) makes sure there are no duplicate entries per timestamp
            cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {tbl} (time TIMESTAMPTZ NOT NULL, PRIMARY KEY (time));"
                                ).format(tbl=sql.Identifier(table_name)))
            # update columns with channel names
            for channel in channels:
                # TODO only float values allowed right now
                cur.execute(sql.SQL("ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {channel} DOUBLE PRECISION;"
                                    ).format(tbl=sql.Identifier(table_name),
                                             channel=sql.Identifier(channel)))
            # create hypertable and index
            cur.execute(sql.SQL("SELECT create_hypertable({tbl},'time', if_not_exists => TRUE);"
                                ).format(tbl=sql.Literal(table_name)))
            cur.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {tbl_time} ON {tbl}(time DESC);"
                                ).format(tbl_time=sql.Identifier(table_name + "_time"),
                                         tbl=sql.Identifier(table_name)))
        conn.commit()

    @staticmethod
    def _iter_wide_rows(arr: np.ndarray, channel_names: Sequence[str]) -> Iterable[tuple]:
        ts_ns = arr["ts"]
        for i in range(ts_ns.shape[0]):
            t = datetime.fromtimestamp(ts_ns[i] / 1e9, tz=timezone.utc)
            vals = []
            for ch in channel_names:
                v = arr[ch][i]
                try:
                    # TODO only float values allowed right now
                    fv = float(v)
                    if math.isnan(fv) or math.isinf(fv):
                        vals.append(None)
                    else:
                        vals.append(fv)
                except (ValueError, TypeError):
                    vals.append(None)
            yield t, *vals

    def _sync_module(self, conn: psycopg.connection.Connection, collector: Collector, module: str):
        self.logger.info("Syncing module %s", module)
        # use collector to merge all channel names from all measurements containing module / topic
        mcap_paths: List[str] = collector.get_mcap_paths_for_module(module, is_finished=True)
        # store channel names per topic
        topics_channels: Dict[str, Set[str]] = defaultdict(set)
        # store latest timestamp per topic
        topics_latest_ns: Dict[str, int] = {}
        # store table names per topic
        topics_tables: Dict[str, str] = {}

        for mcap_file in mcap_paths:
            mcap_reader = collector.get_mcap_reader(mcap_file)
            # we need: all channel names for each topic in mcap file, measurement start/stop times
            for t_name, t in mcap_reader.get_topics().items():
                topics_channels[t_name].update(t.get_fields())  # keep a set of channel names
            # close reader here and only re-open needed readers (normally few)
            mcap_reader.close()

        self.logger.debug(f'Processing topics: {list(topics_channels.keys())}')
        # check if table(s) (one per topic) exist and update schema(s) (channel names)
        for topic_name, channels in topics_channels.items():
            table_name = self._get_table_name_from_topic_module(module, topic_name)
            topics_tables[topic_name] = table_name

            self._create_update_table(conn, table_name, channels)

            # read most recent row --> get timestamp per topic (convert to ns)
            with conn.cursor() as cur:
                cur.execute(sql.SQL("SELECT MAX(time) FROM {tbl};").format(tbl=sql.Identifier(table_name)))
                latest, = cur.fetchone()
            latest_ns = int(latest.timestamp() * 1_000_000) * 1000 if latest else 0
            self.logger.debug("Latest row timestamp (%s): %d ns / %s", table_name, latest_ns, str(latest))
            topics_latest_ns[topic_name] = latest_ns

        if len(topics_latest_ns) == 0:
            self.logger.warning('no topics')
            return

        # build list of measurements to sync: discard all, where stop-time < latest row timestamp
        timestamp_ns_min = 0 if self._force_resync else min(topics_latest_ns.values())
        mcap_paths_to_sync = collector.get_mcap_paths_for_module(module,
                                                                 timestamp_ns_min=timestamp_ns_min,
                                                                 is_finished=True)
        self.logger.info("Found %d new measurements to sync", len(mcap_paths_to_sync))

        for mcap_file in mcap_paths_to_sync:
            mcap_reader = collector.get_mcap_reader(mcap_file)
            with self.time_it("Ingest file", limit_ms=0, log_severity=logging.DEBUG):
                for topic_name, latest_ns in topics_latest_ns.items():
                    self.logger.info("Ingest data from %s, topic %s", mcap_file, topic_name)

                    # check if most recent row in table is in a measurement (upload was interrupted)
                    if mcap_reader.time_end_ns < latest_ns and not self._force_resync:
                        self.logger.info("Topic %s selected, but already fully synced. Measurement: %s",
                                         topic_name, mcap_file)
                        continue

                    # sync measurement. increase minimum read timestamp by 1us (database precision) to avoid duplicates
                    timestamp_ns_min = 0 if self._force_resync else latest_ns + 1000
                    for chunk in mcap_reader.get_data_chunked(topic_name, chunk_size_megabytes=100,
                                                              timestamp_ns_min=timestamp_ns_min):
                        if self._thread_stop_event.is_set() or self._sync_stop_ev.is_set():
                            break

                        if chunk is None:
                            self.logger.error(f"Failed to sync {mcap_file}, topic {topic_name}: chunk is None")
                            break

                        try:
                            with conn.cursor() as cursor:
                                # channel columns = all except 'ts'
                                channel_names = [n for n in chunk.dtype.names if n != "ts"]
                                if not channel_names:
                                    break
                                cols = ["time"] + channel_names
                                column_list = sql.SQL(", ").join(sql.Identifier(c) for c in cols)
                                rows_ingested = 0
                                with cursor.copy(sql.SQL("COPY {} ({}) FROM STDIN").format(
                                        sql.Identifier(topics_tables[topic_name]), column_list)
                                ) as copy:
                                    for row in self._iter_wide_rows(chunk, channel_names):
                                        copy.write_row(row)
                                        rows_ingested += 1
                                self.logger.info("Ingested %d rows from topic %s, %s",
                                                 rows_ingested, topic_name, mcap_file)
                            conn.commit()
                        except Exception as copy_error:
                            # note: on duplicate timestamp, COPY command fails with "UniqueViolation"
                            self.logger.error(f"ERROR: COPY command failed: {type(copy_error).__name__}: {copy_error}")
                            conn.rollback()  # clear aborted transaction so later operations work
            # discard read data before loading next
            mcap_reader.close()

            if self._thread_stop_event.is_set() or self._sync_stop_ev.is_set():
                break

    def _worker_thread_fn(self):
        self.logger.debug('worker thread running')

        # Startup: try connection to DB until it works or shutdown event is set
        _user = self.config_handler.config['db_user']
        _pw = self.config_handler.config['db_password']
        _host = self.config_handler.config['db_host_port']
        _db = self.config_handler.config['db_name']
        dsn = f"postgresql://{_user}:{_pw}@{_host}/{_db}"

        # stay in loop until thread is stopped
        while not self._thread_stop_event.is_set():
            self.module_interface.set_ready_state(True)
            self.logger.info("sync worker in idle: waiting for start signal")

            # wait for trigger or shutdown
            while not self._thread_stop_event.is_set():
                self._sync_start_ev.wait(0.2)
                if self._sync_start_ev.is_set():
                    self._sync_start_ev.clear()
                    break

            if self._thread_stop_event.is_set():
                return

            self.module_interface.set_ready_state(False)
            # if configured, wait a little
            self._thread_stop_event.wait(self.config_handler.config['delay_before_start_s'])

            # startup checks
            self.logger.info("Starting sync: check DB connection")
            while not self._thread_stop_event.is_set() and not self._sync_stop_ev.is_set():
                try:
                    self._try_database_connection(dsn)
                    break
                except Exception as e:
                    self.logger.warning(f"Failed to connect to DB {type(e).__name__}: {e}, retrying in 10 seconds...")
                    self._sync_stop_ev.wait(10)

            if self._thread_stop_event.is_set():
                return
            if self._sync_stop_ev.is_set():
                continue

            # perform sync
            self.logger.info("Parsing data directory")
            try:
                collector = Collector()
                collector.parse_directory(self.module_interface.data_dir)

                # connect to DB
                with psycopg.connect(dsn) as conn:
                    # handle all configured modules
                    for module in self.config_handler.config['sync_modules']:
                        if self._sync_stop_ev.is_set():
                            break
                        self._sync_module(conn, collector, module)
                        conn.commit()

                self.logger.info("Sync completed")
            except Exception as e:
                self.logger.error(f"Failed sync {type(e).__name__}: {e}\n{traceback.format_exc()}")
                continue

        # TODO data-in status update

    def _start_thread(self, locking=True):
        if locking:
            self._thread_handling_lock.acquire()

        if self._worker_thread and self._worker_thread.is_alive():
            self.logger.warning('_start_thread: thread already running')
        else:
            self._worker_thread = threading.Thread(target=self._worker_thread_fn, name='worker')
            self._thread_stop_event.clear()
            self._sync_start_ev.clear()
            self._sync_stop_ev.clear()
            self._worker_thread.start()

        if locking:
            self._thread_handling_lock.release()

    def _stop_thread(self, locking=True):
        if locking:
            self._thread_handling_lock.acquire()

        if self._worker_thread:
            self._thread_stop_event.set()
            self._stop_sync()
            self._worker_thread.join()
            self._worker_thread = None

        if locking:
            self._thread_handling_lock.release()

    def command_validate_config(self, config: Dict) -> Status:
        if config['delay_before_start_s'] < 0:
            return Status(error=True, title="Invalid delay_before_start_s",
                          message="Delay before start must be non-negative")

        if (len(config['db_host_port']) == 0 or
                ':' not in config['db_host_port'] or
                not config['db_host_port'].split(':')[1].isdigit()):
            return Status(error=True, title="Invalid db_host_port",
                          message="DB host and port must be specified")

        if len(config['db_user']) == 0:
            return Status(error=True, title="Invalid db_user", message="DB user must be specified")

        if len(config['db_password']) == 0:
            return Status(error=True, title="Invalid db_password", message="DB password must be specified")

        if len(config['db_name']) == 0:
            return Status(error=True, title="Invalid db_name", message="DB name must be specified")

        for module in config['sync_modules']:
            if len(module) == 0:
                return Status(error=True, title="Invalid sync_modules", message="Module name must not be empty")

        return Status(error=False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            # make sure thread re-spawn is not intercepted by command_prepare_sampling
            with self._thread_handling_lock:
                self._stop_thread(locking=False)
                self._start_thread(locking=False)

            return Status(error=False)

        except Exception as e:
            self.logger.error(f'error applying config: {type(e).__name__}: {e}\n{traceback.format_exc()}')
            return Status(error=True, title=type(e).__name__, message=str(e))

    def _start_sync(self, force_resync=False):
        self.logger.info('Start syncing!')
        self._sync_stop_ev.clear()
        self._force_resync = force_resync
        self._sync_start_ev.set()

    def _stop_sync(self):
        self.logger.info('Stop syncing!')
        self._sync_start_ev.clear()
        self._sync_stop_ev.set()

    def command_config_event(self, cfg_key: str) -> None:
        self.logger.debug('Received event_data: %s', cfg_key)

        if cfg_key == 'button_start':
            self._start_sync()
        elif cfg_key == 'button_stop':
            self._stop_sync()
        elif cfg_key == 'button_resync':
            self._start_sync(force_resync=True)
        else:
            self.logger.warning('Received unknown config event.')

    def command_state_change(self, command: StartStopCmd, related_state: MeasurementStateType) -> None:
        if related_state == MeasurementStateType.CAPTURING and command == StartStopCmd.STOP:
            if self.config_handler.config['sync_on_capture_stop']:
                self._start_sync()

    def command_get_meta_data(self) -> ModuleMetaFactory:
        meta_cfg = ModuleMetaFactory()
        return meta_cfg

    def command_get_schemas(self) -> List[Dict]:
        return [{
            'type': 'object',
            'properties': {
                # TODO list all possible channel names and data types ('number', 'integer', 'string')
                # 'my_channel': {'type': 'number'}
            }
        }]


if __name__ == '__main__':
    main(DatabaseSync, DatabaseSyncConfig, environ.to_config(ModuleEnv).MODULE_NAME)
