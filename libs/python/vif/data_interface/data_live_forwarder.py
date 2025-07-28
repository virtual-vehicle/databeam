import os
import time
import threading
import multiprocessing
import multiprocessing.synchronize
import queue
import signal
import traceback
from typing import Optional, Dict, List
from dataclasses import dataclass

import orjson

from vif.logger.logger import LoggerMixin, log_reentrant
from vif.data_interface.connection_manager import ConnectionManager, Key
from vif.asyncio_helpers.asyncio_helpers import tick_generator
from vif.data_interface.network_messages import ModuleDataConfig, GetSchemasReply
from vif.data_interface.helpers import empty_queue, check_leftover_threads


class LiveProcess(LoggerMixin, multiprocessing.Process):
    def __init__(self, *args,
                 shutdown_ev: multiprocessing.synchronize.Event,
                 process_ready_event: multiprocessing.synchronize.Event,
                 possible_schema_change_event: multiprocessing.synchronize.Event,
                 data_live_queue: multiprocessing.Queue,
                 config_live_queue: multiprocessing.Queue,
                 db_id: str,
                 db_router: str,
                 module_name: str,
                 **kwargs):
        super().__init__(*args, logger_name='DataBroker.live_proc', **kwargs)
        LoggerMixin.configure_logger(level=os.getenv('LOGLEVEL'))

        self.shutdown_ev: multiprocessing.synchronize.Event = shutdown_ev
        self.process_ready_event: multiprocessing.synchronize.Event = process_ready_event
        self.possible_schema_change_event: multiprocessing.synchronize.Event = possible_schema_change_event
        self.data_live_queue: multiprocessing.Queue = data_live_queue
        self.config_live_queue: multiprocessing.Queue = config_live_queue
        self.db_id: str = db_id
        self.db_router: str = db_router
        self.module_name: str = module_name

        # initialized in run(), in new process:
        self.cm = None
        self.live_frequency_hz = None
        self.data_updated_dec_available = None
        self.thread_live_dec_kill = None
        self.enable_live_all = None
        self.enable_fixed_rate = None
        self.thread_live_dec_list = None
        self.available_schema_topics = None
        self.schema_data = None

    def run(self):
        self.logger.info('starting live-data process for %s/%s', self.db_id, self.module_name)

        signal.signal(signal.SIGINT, lambda signum, frame: (self.shutdown_ev.set(),
                                                            log_reentrant(f'signal {signum} called')))
        signal.signal(signal.SIGTERM, lambda signum, frame: (self.shutdown_ev.set(),
                                                             log_reentrant(f'signal {signum} called')))

        self.cm = ConnectionManager(router_hostname=self.db_router, db_id=self.db_id, shutdown_event=self.shutdown_ev,
                                    logger_name='ConnectionManagerLive', node_name=f"m/{self.module_name}_live_data",
                                    max_parallel_queryables=0, max_parallel_req=1)

        self.live_frequency_hz = 1.0
        self.data_updated_dec_available: List[bool] = []
        self.thread_live_dec_kill = threading.Event()
        self.enable_live_all = False
        self.enable_fixed_rate = False
        self.available_schema_topics: List[str] = []
        self.schema_data: list = []
        self.thread_live_dec_list: List[threading.Thread] = []

        thread_receiver: Optional[threading.Thread] = None
        thread_receiver_kill = threading.Event()

        # signal that process is ready
        self.process_ready_event.set()

        while not self.shutdown_ev.is_set():
            try:
                # receive config updates
                cfg: Optional[ModuleDataConfig] = None
                try:
                    cfg = self.config_live_queue.get(timeout=0.2)
                except queue.Empty:
                    pass

                # If a possible schema change was flagged from the module (e.g. by applying the config)
                if self.possible_schema_change_event.is_set():
                    new_available_schema_topics: List[str] = self._receive_module_schemas()

                    # If the fetched schema is different from the current schema
                    if new_available_schema_topics != self.available_schema_topics:
                        self.logger.debug("Schema changed. Restarting live publishers.")

                        if thread_receiver is not None:
                            thread_receiver_kill.set()
                            thread_receiver.join()
                        thread_receiver = None

                        self._stop_live_dec_threads()

                        # Schema changed - update schema info and restart all forwarding threads
                        self.available_schema_topics = new_available_schema_topics
                        self.schema_data = [None for _ in self.available_schema_topics]
                        self.data_updated_dec_available = [False for _ in self.available_schema_topics]

                        empty_queue(self.data_live_queue)

                    self.possible_schema_change_event.clear()

                # If a new live config was received
                if cfg is not None:
                    self.logger.debug('got config: %s', cfg.serialize())

                    self.enable_live_all = cfg.enable_live_all_samples
                    self.enable_fixed_rate = cfg.enable_live_fixed_rate

                    if abs(self.live_frequency_hz - cfg.live_rate_hz) > 1e-3:
                        # update rate changed - restart thread!
                        self.live_frequency_hz = cfg.live_rate_hz
                        self._stop_live_dec_threads()

                # If the "receiver" thread, which polls from the live data in queue is closed for any reason, start it
                if thread_receiver is None:
                    thread_receiver = threading.Thread(target=self._thread_receiver, name='live_receiver',
                                                       args=[thread_receiver_kill])
                    thread_receiver_kill.clear()
                    thread_receiver.start()

                # Start or close the live dec threads
                if self.enable_fixed_rate and len(self.thread_live_dec_list) == 0:
                    self.thread_live_dec_kill.clear()
                    for schema_id in range(len(self.available_schema_topics)):
                        thread_live_dec = threading.Thread(target=self._thread_live_decimated,
                                                           name=f'live_dec_{schema_id}',
                                                           args=[schema_id])
                        self.thread_live_dec_list.append(thread_live_dec)
                        thread_live_dec.start()
                elif not self.enable_fixed_rate and len(self.thread_live_dec_list) > 0:
                    self._stop_live_dec_threads()

            except Exception as e:
                self.logger.error(f'EX {type(e).__name__}: {e}\n{traceback.format_exc()}')

        # clean up
        self.logger.debug('cleaning up')
        if thread_receiver is not None:
            thread_receiver.join()
        self.logger.debug('thread_receiver joined')
        self._stop_live_dec_threads()
        self.logger.debug('all thread_live_dec joined')
        self.logger.debug('all threads joined')

        self.cm.close()

        self.process_ready_event.clear()
        for q in [self.data_live_queue, self.config_live_queue]:
            empty_queue(q)
            q.close()

        self.logger.info('finished live-data process for %s', self.module_name)
        self.logger.debug(check_leftover_threads())

    def _receive_module_schemas(self) -> List[str]:
        module_schemas = self.cm.request(Key(self.db_id, f'm/{self.module_name}', "get_schemas"))
        if module_schemas is None:
            return []
        return GetSchemasReply.deserialize(module_schemas).get_topic_names_list()

    def _thread_receiver(self, thread_receiver_kill: threading.Event):
        self.logger.info('_thread_receiver start')

        schema_network_topic_keys_liveall: List[Key] = []
        schema_network_topic_ids_liveall: List[int] = []

        for schema_name in self.available_schema_topics:
            key = Key(self.db_id, f"m/{self.module_name}/{schema_name}", "liveall")
            schema_network_topic_keys_liveall.append(key)

            pub_id: int = self.cm.declare_publisher(key)
            schema_network_topic_ids_liveall.append(pub_id)

        while not self.shutdown_ev.is_set() and not thread_receiver_kill.is_set():
            try:
                try:
                    raw: LiveDataContainer = self.data_live_queue.get(timeout=0.2)
                except queue.Empty:
                    continue  # no data - check event and try again
                if raw is None:
                    self.logger.info('stopping process')
                    break

                # TODO maybe change to s/t else to split up sync of threads to sync with parent process?
                if self.possible_schema_change_event.is_set():
                    continue

                curr_schema_id: int = raw.schema_id
                time_ns: int = raw.time_ns
                data: Dict = raw.data
                data['ts'] = time_ns

                self.schema_data[curr_schema_id] = orjson.dumps(data)
                self.data_updated_dec_available[curr_schema_id] = True

                # publish "live all" data
                if self.enable_live_all:
                    with self.time_it(f'live all publish schema {curr_schema_id}', limit_ms=1):
                        self.cm.publish(schema_network_topic_keys_liveall[curr_schema_id],
                                        self.schema_data[curr_schema_id])
            except Exception as _e:
                self.logger.error(f'EX receiver {type(_e).__name__}: {_e}\n{traceback.format_exc()}')

        for pub_id in schema_network_topic_ids_liveall:
            self.cm.undeclare_publisher(pub_id)

    def _thread_live_decimated(self, responsible_schema_id: int):
        self.logger.info(f'live forwarding decimated for schema {responsible_schema_id}')

        schema_name = self.available_schema_topics[responsible_schema_id]
        schema_network_topic_key_livedec = Key(self.db_id, f"m/{self.module_name}/{schema_name}", "livedec")
        schema_network_topic_id_livedec = self.cm.declare_publisher(schema_network_topic_key_livedec)

        g = tick_generator(1.0 / self.live_frequency_hz, drop_missed=True, time_source=time.time)
        while not self.thread_live_dec_kill.is_set():
            try:
                self.thread_live_dec_kill.wait(timeout=next(g))
                if self.possible_schema_change_event.is_set():
                    continue
                if not self.data_updated_dec_available[responsible_schema_id]:
                    continue
                if self.schema_data[responsible_schema_id] is None:
                    continue
                # current_data is not changed but recreated - holding reference as copy is ok
                self.data_updated_dec_available[responsible_schema_id] = False
                # logger.debug('send decimated: %s', current_data)
                with self.time_it(f'live dec publish schema {responsible_schema_id}', limit_ms=1):
                    self.cm.publish(schema_network_topic_key_livedec, self.schema_data[responsible_schema_id])
            except Exception as _e:
                self.logger.error(f'EX live_decimated ({responsible_schema_id}) {type(_e).__name__}: {_e}\n'
                                  f'{traceback.format_exc()}')
        g.close()
        self.cm.undeclare_publisher(schema_network_topic_id_livedec)

    def _stop_live_dec_threads(self):
        if len(self.thread_live_dec_list) > 0:
            self.thread_live_dec_kill.set()
            for dec_thread in self.thread_live_dec_list:
                dec_thread.join()
            self.thread_live_dec_list.clear()


@dataclass
class LiveDataContainer:
    schema_id: int
    time_ns: int
    data: Dict


class DataLiveForwarder(LoggerMixin):
    def __init__(self, *args, module_name: str, db_id: str, db_router: str,
                 child_shutdown_ev: multiprocessing.Event, schema_change_ev: multiprocessing.Event, **kwargs):
        super().__init__(*args, **kwargs)

        self.module_name = module_name
        self._child_shutdown_ev: multiprocessing.Event() = child_shutdown_ev

        # create live data process
        self._live_active = False
        self._live_queue: multiprocessing.Queue[LiveDataContainer] = multiprocessing.Queue(maxsize=1000)
        self._live_config_queue: multiprocessing.Queue[ModuleDataConfig] = multiprocessing.Queue(maxsize=4)
        self._live_process_ready_event = multiprocessing.Event()
        self._live_proc = LiveProcess(shutdown_ev=self._child_shutdown_ev,
                                      process_ready_event=self._live_process_ready_event,
                                      possible_schema_change_event=schema_change_ev,
                                      data_live_queue=self._live_queue,
                                      config_live_queue=self._live_config_queue,
                                      db_id=db_id,
                                      db_router=db_router,
                                      module_name=self.module_name)

    def start_process(self):
        self.logger.info('starting live-data process')
        self._live_proc.start()
        # wait for process to start
        self._live_process_ready_event.wait(timeout=10)  # this should take about 1 second
        if self._live_process_ready_event.is_set():
            self.logger.info('starting live-data process succeeded')
        else:
            raise RuntimeError('starting live-data process failed (timeout)')

    def toggle_active(self, active: bool):
        self._live_active = active

    def is_active(self) -> bool:
        return self._live_active

    def configure_live(self, data_config: ModuleDataConfig):
        self.logger.debug('configure_live: %s', data_config.serialize())
        self._live_config_queue.put(data_config)
        if data_config.enable_live_all_samples or data_config.enable_live_fixed_rate:
            self.toggle_active(True)
        else:
            self.toggle_active(False)

    def forward_data(self, time_ns: int, schema_index: int, data: Dict):
        try:
            live_data: LiveDataContainer = LiveDataContainer(schema_index, time_ns, data)
            self._live_queue.put_nowait(live_data)
        except Exception as e:
            self.logger.error(f'EX data_in live {type(e).__name__}: {e}')

    def close(self):
        self.logger.debug('emptying live data queues')

        for q in [self._live_queue, self._live_config_queue]:
            # _empty_queue(q) # ?? do not empty from this side
            q.close()

        if self._live_proc is not None:
            if self._live_proc.is_alive():
                self.logger.debug('joining live-data process')
                self._live_proc.join()
                self.logger.debug('joined live-data process')
            self._live_proc.close()

        self.logger.info('close live data forwarder succeeded')
