import json
import os
import time
import logging
import threading
import multiprocessing
import multiprocessing.synchronize
import queue
import signal
import traceback
from pathlib import Path
import re
from functools import lru_cache
from typing import Optional, Dict, Tuple, List, Callable
from dataclasses import dataclass
from collections.abc import Iterator
from contextlib import contextmanager
from enum import Enum

from mcap.writer import Writer as McapWriter, CompressionType

from vif.logger.logger import LoggerMixin, log_reentrant
from vif.data_interface.connection_manager import ConnectionManager, Key
from vif.asyncio_helpers.asyncio_helpers import tick_generator
from vif.file_helpers.creation import create_directory
from vif.data_interface.network_messages import ModuleDataConfig


def _empty_queue(q):
    while not q.empty():
        try:
            q.get_nowait()
        except queue.Empty:
            pass


@contextmanager
def time_it(logger_fn: Callable, prefix: str, limit_ms: float) -> Iterator[None]:
    tic: int = time.perf_counter_ns()
    try:
        yield
    finally:
        toc: int = time.perf_counter_ns()
        if toc - tic > limit_ms * 1e6:
            logger_fn(f"%s took = %.3f ms", prefix, (toc - tic) / 1e6)


def _check_leftover_threads() -> str:
    num_threads_left = threading.active_count() - 1
    ret_str = f'done - threads left: {num_threads_left}'
    if num_threads_left > 0:
        ret_str += f'\nthreads left: {[thread.name for thread in threading.enumerate()]}'
    return ret_str


@dataclass
class CaptureCommand:
    class Command(Enum):
        START = 0
        STOP = 1

    cmd: Command
    measurement_name: str = ''
    measurement_dir: Path = Path()
    module_data_schemas: Optional[List] = None


def _capture_proc(shutdown_ev: multiprocessing.synchronize.Event,
                  process_ready_event: multiprocessing.synchronize.Event,
                  data_capture_queue: multiprocessing.Queue,
                  config_capture_queue: multiprocessing.Queue,
                  module_name: str,
                  module_type: str) -> None:
    LoggerMixin.configure_logger(level=os.getenv('LOGLEVEL'))
    logger = logging.getLogger('DataBroker.capture_proc')
    logger.info('started capturing process for %s', module_name)

    signal.signal(signal.SIGINT, lambda signum, frame: (shutdown_ev.set(), log_reentrant(f'signal {signum} called')))
    signal.signal(signal.SIGTERM, lambda signum, frame: (shutdown_ev.set(), log_reentrant(f'signal {signum} called')))

    thread_capture_kill_ev = threading.Event()
    thread_capture: Optional[threading.Thread] = None

    # signal that process is ready
    process_ready_event.set()

    def _capture_thread(measurement_name: str, measurement_dir: Path, module_data_schemas: List):
        nonlocal process_ready_event, data_capture_queue, shutdown_ev, thread_capture_kill_ev
        cap_logger = logging.getLogger('DataBroker.capture_thread')
        cap_logger.info('starting thread for %s', measurement_name)
        try:
            # make sure directory exists
            create_directory(Path(measurement_dir))
            # save as ".partXXXX.mcap" file and move when done
            temp_filename_ts = time.time_ns()
            temp_filename = f'{module_name}.part{temp_filename_ts}.mcap'
            mcap_file = open(measurement_dir / temp_filename, 'wb')
            json_channel_ids = []

            writer = McapWriter(mcap_file, compression=CompressionType.ZSTD, use_chunking=True)
            writer.start()
            # create a schema for each in list
            for idx, s in enumerate(module_data_schemas):
                new_schema = writer.register_schema(
                    name=f'{module_type}_{idx}' if 'dtype_name' not in s else s['dtype_name'],
                    encoding='jsonschema',
                    data=json.dumps(s).encode())
                cap_logger.info(f'new schema: {new_schema} with topic: '
                                f'{module_type if "topic" not in s else s["topic"]}')
                json_channel_ids.append(writer.register_channel(
                    schema_id=new_schema,
                    topic=module_name if 'topic' not in s else s['topic'],
                    message_encoding='json',
                ))
        except Exception as _e:
            cap_logger.error(f'EX thread setup {type(_e).__name__}: {_e}\n{traceback.format_exc()}')
            return

        process_ready_event.set()

        while not thread_capture_kill_ev.is_set():
            try:
                try:
                    raw = data_capture_queue.get(timeout=0.2)
                except queue.Empty:
                    continue  # no data - check event and try again
                if raw is None:
                    cap_logger.error('received None')
                    continue

                time_ns = raw[0]
                data = raw[1]
                schema_idx = raw[2]

                assert isinstance(data, dict)
                try:
                    # catch NaN values and drop
                    data_json = json.dumps(data, allow_nan=False).encode('utf-8')
                    writer.add_message(
                        channel_id=json_channel_ids[schema_idx],
                        data=data_json,
                        log_time=time_ns, publish_time=time_ns
                    )
                except ValueError as _e:
                    cap_logger.error(f'EX JSON writer {type(_e).__name__}: NaN in {data}')

                # TODO file rotation

            except Exception as _e:
                cap_logger.error(f'EX {type(_e).__name__}: {_e}\n{traceback.format_exc()}')

        if thread_capture_kill_ev.is_set():
            cap_logger.debug('thread capture kill event was set')

        # close file etc.
        writer.finish()
        mcap_file.close()
        # rename partial file to .mcap when done
        # check if file already exists (previous crash and/or relaunch)
        if Path(measurement_dir / f'{module_name}.mcap').exists():
            cap_logger.warning('finished MCAP file already exists: %s.mcap', module_name)
            os.rename(measurement_dir / temp_filename, measurement_dir / f'{module_name}.{temp_filename_ts}.mcap')
        else:
            os.rename(measurement_dir / temp_filename, measurement_dir / f'{module_name}.mcap')
        cap_logger.info('finished capturing thread for %s', measurement_name)

    # handle command queue
    while not shutdown_ev.is_set():
        try:
            try:
                cap_cmd: CaptureCommand = config_capture_queue.get(timeout=0.2)
            except queue.Empty:
                continue  # no data - check event and try again

            logger.debug('got command %s', cap_cmd)

            if cap_cmd.cmd == CaptureCommand.Command.STOP:
                logger.info('processing STOP')
                thread_capture_kill_ev.set()
                if thread_capture is not None:
                    thread_capture.join()
                    thread_capture = None
            elif cap_cmd.cmd == CaptureCommand.Command.START:
                logger.info('processing START')
                assert thread_capture is None
                thread_capture = threading.Thread(target=_capture_thread, args=(
                    cap_cmd.measurement_name,
                    cap_cmd.measurement_dir,
                    cap_cmd.module_data_schemas), name='capture_thread')
                thread_capture_kill_ev.clear()
                thread_capture.start()
            else:
                raise ValueError(f'unknown command: {cap_cmd.cmd.name}')

            logger.debug('processed command: %s', cap_cmd.cmd.name)
        except Exception as e:
            logger.error(f'EX cap-command {type(e).__name__}: {e}\n{traceback.format_exc()}')

    logger.info('cleaning up')
    thread_capture_kill_ev.set()
    if thread_capture is not None:
        thread_capture.join()

    process_ready_event.clear()
    for q in [data_capture_queue, config_capture_queue]:
        _empty_queue(q)
        q.close()

    logger.info('finished capturing process for %s', module_name)
    logger.debug(_check_leftover_threads())


def _live_proc(shutdown_ev: multiprocessing.synchronize.Event,
               process_ready_event: multiprocessing.synchronize.Event,
               data_live_queue: multiprocessing.Queue,
               config_live_queue: multiprocessing.Queue,
               db_id: str,
               db_router: str,
               module_name: str) -> None:
    LoggerMixin.configure_logger(level=os.getenv('LOGLEVEL'))
    logger = logging.getLogger('DataBroker.live_proc')
    logger.info('starting live-data process for %s/%s', db_id, module_name)

    signal.signal(signal.SIGINT, lambda signum, frame: (shutdown_ev.set(), log_reentrant(f'signal {signum} called')))
    signal.signal(signal.SIGTERM, lambda signum, frame: (shutdown_ev.set(), log_reentrant(f'signal {signum} called')))

    cm = ConnectionManager(router_hostname=db_router, db_id=db_id, shutdown_event=shutdown_ev,
                           logger_name='ConnectionManagerLive')
    pub_key_liveall = Key(db_id, f'm/{module_name}', 'liveall')
    pub_key_livedec = Key(db_id, f'm/{module_name}', 'livedec')
    cm.declare_publisher(pub_key_liveall)
    cm.declare_publisher(pub_key_livedec)
    logger.debug('connection init done')

    live_frequency_hz = 1.0
    current_data: Optional[str] = None
    data_update_lock = threading.Lock()
    data_updated_dec_available = False
    thread_live_dec_kill = threading.Event()
    enable_live_all = False
    thread_live_dec: Optional[threading.Thread] = None

    def _thread_receiver():
        nonlocal cm, current_data, data_update_lock, data_updated_dec_available, enable_live_all
        logger.info('_thread_receiver start')
        while not shutdown_ev.is_set():
            try:
                try:
                    raw = data_live_queue.get(timeout=0.2)
                except queue.Empty:
                    continue  # no data - check event and try again
                if raw is None:
                    logger.info('stopping process')
                    break

                time_ns: int = raw[0]
                data: Dict = raw[1]

                data['ts'] = time_ns

                with data_update_lock:
                    current_data = json.dumps(data)
                    data_updated_dec_available = True

                # publish "live all" data
                if enable_live_all:
                    with time_it(logger.warning, 'live all publish', limit_ms=1):
                        cm.publish(pub_key_liveall, current_data)

            except Exception as _e:
                logger.error(f'EX receiver {type(_e).__name__}: {_e}\n{traceback.format_exc()}')
                break

    def _thread_live_decimated():
        nonlocal cm, current_data, data_update_lock, data_updated_dec_available
        logger.info('live forwarding decimated')
        t_delta = 1 / live_frequency_hz
        g = tick_generator(t_delta, drop_missed=True, time_source=time.time)
        last_exec_time = time.time()
        while not thread_live_dec_kill.is_set():
            try:
                thread_live_dec_kill.wait(timeout=next(g))
                now = time.time()
                if now > last_exec_time + t_delta * 1.5:
                    logger.warning('live_decimated took too long by %.3f s', now - (last_exec_time + t_delta))
                last_exec_time = now
                with data_update_lock:
                    if not data_updated_dec_available or current_data is None:
                        continue
                    # current_data is not changed but recreated - holding reference as copy is ok
                    current_data_copy = current_data
                    data_updated_dec_available = False
                # logger.debug('send decimated: %s', current_data)
                with time_it(logger.debug, 'live dec publish', limit_ms=1):
                    cm.publish(pub_key_livedec, current_data_copy)
            except Exception as _e:
                logger.error(f'EX live_decimated {type(_e).__name__}: {_e}\n{traceback.format_exc()}')
                break
        g.close()

    try:
        thread_receiver = threading.Thread(target=_thread_receiver, name='live_receiver')
        thread_receiver.start()
    except Exception as e:
        logger.error(f'EX proc setup {type(e).__name__}: {e}\n{traceback.format_exc()}')
        return

    # signal that process is ready
    process_ready_event.set()

    while not shutdown_ev.is_set():
        try:
            # receive config updates
            try:
                cfg: ModuleDataConfig = config_live_queue.get(timeout=0.2)
            except queue.Empty:
                continue  # no data - check event and try again
            if cfg is None:
                logger.info('received None: ignore')
                continue
            logger.debug('got config: %s', cfg.serialize())

            enable_live_all = cfg.enable_live_all_samples

            if abs(live_frequency_hz - cfg.live_rate_hz) > 1e-3:
                # update rate changed - restart thread!
                live_frequency_hz = cfg.live_rate_hz
                if thread_live_dec is not None:
                    thread_live_dec_kill.set()
                    thread_live_dec.join()
                thread_live_dec = None

            if cfg.enable_live_fixed_rate and thread_live_dec is None:
                thread_live_dec = threading.Thread(target=_thread_live_decimated, name='live_dec')
                thread_live_dec_kill.clear()
                thread_live_dec.start()
            elif not cfg.enable_live_fixed_rate and thread_live_dec is not None:
                thread_live_dec_kill.set()
                thread_live_dec.join()
                thread_live_dec = None

        except Exception as e:
            logger.error(f'EX {type(e).__name__}: {e}\n{traceback.format_exc()}')

    # clean up
    logger.debug('cleaning up')
    if thread_receiver is not None:
        thread_receiver.join()
    logger.debug('thread_receiver joined')
    if thread_live_dec is not None:
        thread_live_dec_kill.set()
        thread_live_dec.join()
    logger.debug('thread_live_dec joined')
    logger.debug('all threads joined')

    cm.close()

    process_ready_event.clear()
    for q in [data_live_queue, config_live_queue]:
        _empty_queue(q)
        q.close()

    logger.info('finished live-data process for %s', module_name)
    logger.debug(_check_leftover_threads())


class DataBroker(LoggerMixin):
    def __init__(self, *args, db_id: str, db_router: str, data_dir: Path, module_name: str, module_type: str,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.data_dir = data_dir
        self.module_name = module_name
        self.module_type = module_type

        # replace the following characters in channel names for mcap compatibility
        self._replace_name_chars_re = re.compile(r'[^a-zA-Z0-9_-]')
        self._latest_data: Optional[Tuple[int, Dict]] = None

        self._child_shutdown_ev = multiprocessing.Event()
        # create capturing process
        self._capturing_active = False
        self._capture_queue: multiprocessing.Queue[Tuple[int, Dict, int]] = multiprocessing.Queue(maxsize=100000)
        self._capture_config_queue: multiprocessing.Queue[CaptureCommand] = multiprocessing.Queue(maxsize=4)
        self._capture_process_ready_event = multiprocessing.Event()
        self._capture_proc = multiprocessing.Process(target=_capture_proc,
                                                     kwargs={'shutdown_ev': self._child_shutdown_ev,
                                                             'process_ready_event': self._capture_process_ready_event,
                                                             'data_capture_queue': self._capture_queue,
                                                             'config_capture_queue': self._capture_config_queue,
                                                             'module_name': self.module_name,
                                                             'module_type': self.module_type
                                                             })

        # create live data process
        self._live_active = False
        self._live_queue: multiprocessing.Queue[Tuple[int, Dict]] = multiprocessing.Queue(maxsize=10)
        self._live_config_queue: multiprocessing.Queue[ModuleDataConfig] = multiprocessing.Queue(maxsize=4)
        self._live_process_ready_event = multiprocessing.Event()
        self._live_proc = multiprocessing.Process(target=_live_proc,
                                                  kwargs={'shutdown_ev': self._child_shutdown_ev,
                                                          'process_ready_event': self._live_process_ready_event,
                                                          'data_live_queue': self._live_queue,
                                                          'config_live_queue': self._live_config_queue,
                                                          'db_id': db_id,
                                                          'db_router': db_router,
                                                          'module_name': self.module_name})

    def start_processes(self):
        self.logger.info('starting capture process')
        self._capture_proc.start()
        # wait for process to start
        self._capture_process_ready_event.wait(timeout=6)  # this should take about 0.5 seconds max.
        if self._capture_process_ready_event.is_set():
            self.logger.info('starting capture process succeeded')
        else:
            raise RuntimeError('starting capture process failed (timeout)')
        self._capture_process_ready_event.clear()

        self.logger.info('starting live-data process')
        self._live_proc.start()
        # wait for process to start
        self._live_process_ready_event.wait(timeout=6)  # this should take about 1 second
        if self._live_process_ready_event.is_set():
            self.logger.info('starting live-data process succeeded')
        else:
            raise RuntimeError('starting live-data process failed (timeout)')

    def get_module_data_dir(self, measurement_name: str) -> Path:
        return self.data_dir / measurement_name / self.module_name

    def prepare_capturing(self, measurement_name: str, data_schemas: List[Dict]):
        if len(measurement_name) == 0:
            raise ValueError('empty measurement name')
        self.logger.info('prepare capturing: %s', measurement_name)

        # send command to start thread to capture process:
        self._capture_process_ready_event.clear()
        self._capture_config_queue.put(
            CaptureCommand(cmd=CaptureCommand.Command.START,
                           measurement_name=measurement_name,
                           measurement_dir=self.get_module_data_dir(measurement_name),
                           module_data_schemas=data_schemas))

        # wait for thread to start
        self._capture_process_ready_event.wait(timeout=1)
        if self._capture_process_ready_event.is_set():
            self.logger.info('prepare capturing succeeded')
        else:
            raise RuntimeError('prepare capturing failed (process ready timeout)')

    def start_capturing(self) -> bool:
        self.logger.debug('start capturing')
        _empty_queue(self._capture_queue)
        self._capturing_active = True
        if self._capture_process_ready_event.is_set():
            return False
        else:
            self.logger.error('start_capturing failed: prepare was never called or failed')
            return True

    def stop_capturing(self):
        self.logger.debug('stop capturing')
        self._capturing_active = False
        # send command to stop capture thread
        self._capture_config_queue.put(CaptureCommand(cmd=CaptureCommand.Command.STOP))

    def configure_live(self, data_config: ModuleDataConfig):
        self.logger.debug('configure_live: %s', data_config.serialize())
        self._live_config_queue.put(data_config)
        if data_config.enable_live_all_samples or data_config.enable_live_fixed_rate:
            self._live_active = True
        else:
            self._live_active = False

    @lru_cache(maxsize=1024)
    def replace_name_chars(self, name):
        return self._replace_name_chars_re.sub('_', name)

    def data_in(self, time_ns: int, data: Dict, schema_index: int = 0,
                mcap: bool = True, live: bool = True, latest: bool = True):
        # check channel names and replace
        # TODO timeit @lru_cache and use replace function
        data = {self.replace_name_chars(key): value for key, value in data.items()}

        # store data as latest data if flag is set
        if latest:
            self._latest_data = (time_ns, data)

        # pass data to worker processes for mcap-writing
        if self._capturing_active and mcap:
            try:
                self._capture_queue.put_nowait((time_ns, data, schema_index))
            except Exception as e:
                self.logger.error(f'EX data_in capture {type(e).__name__}: {e}')

        # forward live-data only if needed
        if self._live_active and live:
            try:
                self._live_queue.put_nowait((time_ns, data))
            except Exception as e:
                self.logger.error(f'EX data_in live {type(e).__name__}: {e}')

    def get_latest(self) -> Tuple[int, Optional[Dict]]:
        if self._latest_data is None:
            return 0, None

        return self._latest_data[0], self._latest_data[1].copy()

    def close(self):
        # stop capturing / live data inputs
        self._capturing_active = False
        self._live_active = False

        # stop child processes
        self._child_shutdown_ev.set()

        # clear multiprocessing queues (or a thread will remain after exit)
        self.logger.debug('emptying queues')
        for q in [self._capture_queue, self._capture_config_queue,
                  self._live_queue, self._live_config_queue]:
            # _empty_queue(q) # ?? do not empty from this side
            q.close()

        if self._capture_proc is not None:
            if self._capture_proc.is_alive():
                self.logger.debug('joining capture process')
                self._capture_proc.join()
                self.logger.debug('joined capture process')
            self._capture_proc.close()
        if self._live_proc is not None:
            if self._live_proc.is_alive():
                self.logger.debug('joining live-data process')
                self._live_proc.join()
                self.logger.debug('joined live-data process')
            self._live_proc.close()

        self.logger.info('close succeeded')
