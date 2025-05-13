import os
import time
import logging
import threading
import multiprocessing
import multiprocessing.synchronize
import queue
import signal
import traceback
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass
from collections.abc import Iterator
from contextlib import contextmanager

import orjson

from vif.logger.logger import LoggerMixin, log_reentrant
from vif.data_interface.connection_manager import ConnectionManager, Key
from vif.asyncio_helpers.asyncio_helpers import tick_generator
from vif.data_interface.network_messages import ModuleDataConfig, GetSchemasReply
from vif.data_interface.helpers import empty_queue, check_leftover_threads


@contextmanager
def time_it(logger_fn: Callable, prefix: str, limit_ms: float) -> Iterator[None]:
    tic: int = time.perf_counter_ns()
    try:
        yield
    finally:
        toc: int = time.perf_counter_ns()
        if toc - tic > limit_ms * 1e6:
            logger_fn(f"%s took = %.3f ms", prefix, (toc - tic) / 1e6)


def _live_proc(shutdown_ev: multiprocessing.synchronize.Event,
               process_ready_event: multiprocessing.synchronize.Event,
               possible_schema_change_event: multiprocessing.synchronize.Event,
               data_live_queue: multiprocessing.Queue,
               config_live_queue: multiprocessing.Queue,
               db_id: str,
               db_router: str,
               module_name: str) -> None:

    def _receive_module_schemas() -> List[str]:
        nonlocal cm, module_name
        module_schemas = cm.request(Key(db_id, f'm/{module_name}', "get_schemas"))
        if module_schemas is None:
            return []
        return GetSchemasReply.deserialize(module_schemas).get_topic_names_list()

    def _thread_receiver():
        nonlocal cm, data_updated_dec_available, enable_live_all
        nonlocal schema_data, schema_network_topic_keys_liveall, thread_receiver_kill, possible_schema_change_event
        logger.info('_thread_receiver start')
        while not shutdown_ev.is_set() and not thread_receiver_kill.is_set():
            try:
                try:
                    raw: LiveDataContainer = data_live_queue.get(timeout=0.2)
                    if possible_schema_change_event.is_set():
                        continue
                except queue.Empty:
                    continue  # no data - check event and try again
                if raw is None:
                    logger.info('stopping process')
                    break

                curr_schema_id: int = raw.schema_id
                time_ns: int = raw.time_ns
                data: Dict = raw.data

                data['ts'] = time_ns

                schema_data[curr_schema_id] = orjson.dumps(data)
                data_updated_dec_available[curr_schema_id] = True

                # publish "live all" data
                if enable_live_all:
                    with time_it(logger.warning, f'live all publish schema {curr_schema_id}', limit_ms=1):
                        cm.publish(schema_network_topic_keys_liveall[curr_schema_id], schema_data[curr_schema_id])
                        #if curr_schema_id == 0:
                        #    # Backwards compatibility feature. Remove after full feature migration!
                        #    cm.publish(default_pub_key_liveall, schema_data[curr_schema_id])

            except Exception as _e:
                logger.error(f'EX receiver {type(_e).__name__}: {_e}\n{traceback.format_exc()}')

    def _thread_live_decimated(responsible_schema_id: int):
        nonlocal cm, data_updated_dec_available
        nonlocal schema_data, schema_network_topic_keys_livedec, possible_schema_change_event
        logger.info(f'live forwarding decimated for schemas {responsible_schema_id}')
        t_delta = 1 / live_frequency_hz
        g = tick_generator(t_delta, drop_missed=True, time_source=time.time)
        last_exec_time = time.time()
        while not thread_live_dec_kill.is_set():
            try:
                thread_live_dec_kill.wait(timeout=next(g))
                if possible_schema_change_event.is_set():
                    continue
                now = time.time()
                if now > last_exec_time + t_delta * 1.5:
                    logger.warning(f'live_decimated for schema {responsible_schema_id} took too long by %.3f s', now - (last_exec_time + t_delta))
                last_exec_time = now
                if not data_updated_dec_available[responsible_schema_id] or schema_data[responsible_schema_id] is None:
                    continue
                # current_data is not changed but recreated - holding reference as copy is ok
                data_updated_dec_available[responsible_schema_id] = False
                # logger.debug('send decimated: %s', current_data)
                with time_it(logger.debug, f'live dec publish {responsible_schema_id}', limit_ms=1):
                    cm.publish(schema_network_topic_keys_livedec[responsible_schema_id], schema_data[responsible_schema_id])
                    #if responsible_schema_id == 0:
                    #    # Backwards compatibility feature. Remove after full feature migration!
                    #    cm.publish(default_pub_key_livedec, schema_data[responsible_schema_id])
            except Exception as _e:
                logger.error(f'EX live_decimated {type(_e).__name__}: {_e}\n{traceback.format_exc()}')
        g.close()

    LoggerMixin.configure_logger(level=os.getenv('LOGLEVEL'))
    logger = logging.getLogger('DataBroker.live_proc')
    logger.info('starting live-data process for %s/%s', db_id, module_name)

    signal.signal(signal.SIGINT, lambda signum, frame: (shutdown_ev.set(), log_reentrant(f'signal {signum} called')))
    signal.signal(signal.SIGTERM, lambda signum, frame: (shutdown_ev.set(), log_reentrant(f'signal {signum} called')))

    cm = ConnectionManager(router_hostname=db_router, db_id=db_id, shutdown_event=shutdown_ev,
                           logger_name='ConnectionManagerLive', node_name=f"m/{module_name}_live_data",
                           max_parallel_queryables=0, max_parallel_req=1)

    default_pub_key_liveall = Key(db_id, f'm/{module_name}', 'liveall')
    default_pub_key_livedec = Key(db_id, f'm/{module_name}', 'livedec')
    cm.declare_publisher(default_pub_key_liveall)
    cm.declare_publisher(default_pub_key_livedec)
    logger.debug('default connection init done')

    live_frequency_hz = 1.0
    data_updated_dec_available: List[bool] = []
    thread_live_dec_kill = threading.Event()
    thread_receiver_kill = threading.Event()
    enable_live_all = False
    enable_fixed_rate = False
    thread_receiver: Optional[threading.Thread] = None
    thread_live_dec_list: List[threading.Thread] = []
    available_schema_topics: List[str] = []
    schema_network_topic_keys_liveall: List[Key] = []
    schema_network_topic_keys_livedec: List[Key] = []
    schema_network_topic_ids_liveall: List[int] = []
    schema_network_topic_ids_livedec: List[int] = []
    schema_data: list = []

    # signal that process is ready
    process_ready_event.set()

    while not shutdown_ev.is_set():
        try:
            # receive config updates
            cfg: Optional[ModuleDataConfig] = None
            try:
                cfg = config_live_queue.get(timeout=0.2)
            except queue.Empty:
                pass

            # If a possible schema change was flagged from the module (e.g. by applying the config)
            if possible_schema_change_event.is_set():
                new_available_schema_topics: List[str] = _receive_module_schemas()
                if len(new_available_schema_topics) == 0:
                    shutdown_ev.wait(0.2)
                    continue # No schemas available - try again

                # If the fetched schema is different than the current schema
                if new_available_schema_topics != available_schema_topics:
                    logger.debug("Schema changed. Restarting live publishers.")
                    # Schema changed - update schema info and restart all forwarding threads
                    available_schema_topics = new_available_schema_topics
                    schema_network_topics = [f"{module_name}/{schema_name}" for schema_name in available_schema_topics]
                    for pub_id in schema_network_topic_ids_liveall:
                        cm.undeclare_publisher(pub_id)
                    for pub_id in schema_network_topic_ids_livedec:
                        cm.undeclare_publisher(pub_id)
                    schema_network_topic_ids_liveall.clear()
                    schema_network_topic_ids_livedec.clear()
                    schema_network_topic_keys_liveall = [Key(db_id, f"m/{topic}", "liveall") for topic in
                                                         schema_network_topics]
                    schema_network_topic_keys_livedec = [Key(db_id, f"m/{topic}", "livedec") for topic in
                                                         schema_network_topics]
                    for topic in schema_network_topic_keys_liveall:
                        pub_id: int = cm.declare_publisher(topic)
                        schema_network_topic_ids_liveall.append(pub_id)
                    for topic in schema_network_topic_keys_livedec:
                        pub_id: int = cm.declare_publisher(topic)
                        schema_network_topic_ids_livedec.append(pub_id)
                    schema_data = [None for _ in schema_network_topics]
                    data_updated_dec_available = [False for _ in schema_network_topics]

                    if thread_receiver is not None:
                        thread_receiver_kill.set()
                        thread_receiver.join()
                    thread_receiver = None
                    if len(thread_live_dec_list) > 0:
                        thread_live_dec_kill.set()
                        for dec_thread in thread_live_dec_list:
                            dec_thread.join()
                    thread_live_dec_list = []
                    empty_queue(data_live_queue)
                possible_schema_change_event.clear()

            # If a new live config was received
            if cfg is not None:
                logger.debug('got config: %s', cfg.serialize())

                enable_live_all = cfg.enable_live_all_samples
                enable_fixed_rate = cfg.enable_live_fixed_rate

                if abs(live_frequency_hz - cfg.live_rate_hz) > 1e-3:
                    # update rate changed - restart thread!
                    live_frequency_hz = cfg.live_rate_hz
                    if len(thread_live_dec_list) > 0:
                        thread_live_dec_kill.set()
                        for dec_thread in thread_live_dec_list:
                            dec_thread.join()
                    thread_live_dec_list = []

            # If the "receiver" thread, which polls from the live data in queue is closed for any reason, start it
            if thread_receiver is None:
                thread_receiver = threading.Thread(target=_thread_receiver, name='live_receiver')
                thread_receiver_kill.clear()
                thread_receiver.start()

            # Start or close the live dec threads
            if enable_fixed_rate and len(thread_live_dec_list) == 0:
                thread_live_dec_kill.clear()
                for schema_id in range(len(available_schema_topics)):
                    thread_live_dec = threading.Thread(target=_thread_live_decimated, name=f'live_dec_{schema_id}',
                                                       args=[schema_id])
                    thread_live_dec_list.append(thread_live_dec)
                    thread_live_dec.start()
            elif not enable_fixed_rate and len(thread_live_dec_list) > 0:
                thread_live_dec_kill.set()
                for dec_thread in thread_live_dec_list:
                    dec_thread.join()
                thread_live_dec_list = []

        except Exception as e:
            logger.error(f'EX {type(e).__name__}: {e}\n{traceback.format_exc()}')

    # clean up
    logger.debug('cleaning up')
    if thread_receiver is not None:
        thread_receiver.join()
    logger.debug('thread_receiver joined')
    if len(thread_live_dec_list) > 0:
        thread_live_dec_kill.set()
        for dec_thread in thread_live_dec_list:
            dec_thread.join()
    logger.debug('all thread_live_dec joined')
    logger.debug('all threads joined')

    # Undeclare schema publishers
    for pub_id in schema_network_topic_ids_liveall:
        cm.undeclare_publisher(pub_id)
    for pub_id in schema_network_topic_ids_livedec:
        cm.undeclare_publisher(pub_id)
    schema_network_topic_ids_liveall.clear()
    schema_network_topic_ids_livedec.clear()

    cm.close()

    process_ready_event.clear()
    for q in [data_live_queue, config_live_queue]:
        empty_queue(q)
        q.close()

    logger.info('finished live-data process for %s', module_name)
    logger.debug(check_leftover_threads())


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
        self._live_proc = multiprocessing.Process(target=_live_proc,
                                                  kwargs={'shutdown_ev': self._child_shutdown_ev,
                                                          'process_ready_event': self._live_process_ready_event,
                                                          'possible_schema_change_event': schema_change_ev,
                                                          'data_live_queue': self._live_queue,
                                                          'config_live_queue': self._live_config_queue,
                                                          'db_id': db_id,
                                                          'db_router': db_router,
                                                          'module_name': self.module_name})

    def start_process(self):
        self.logger.info('starting live-data process')
        self._live_proc.start()
        # wait for process to start
        self._live_process_ready_event.wait(timeout=6)  # this should take about 1 second
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
