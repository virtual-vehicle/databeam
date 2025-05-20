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
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass
from enum import Enum

import orjson
from mcap.writer import Writer as McapWriter, CompressionType

from vif.logger.logger import LoggerMixin, log_reentrant
from vif.file_helpers.creation import create_directory
from vif.data_interface.helpers import empty_queue, check_leftover_threads


@dataclass
class CaptureCommand:
    class Command(Enum):
        START = 0
        STOP = 1

    cmd: Command
    measurement_name: str = ''
    measurement_dir: Path = Path()
    module_data_schemas: Optional[List] = None


class CaptureProcess(LoggerMixin, multiprocessing.Process):
    def __init__(self, *args,
                 shutdown_ev: multiprocessing.synchronize.Event,
                 process_ready_event: multiprocessing.synchronize.Event,
                 data_capture_queue: multiprocessing.Queue,
                 config_capture_queue: multiprocessing.Queue,
                 module_name: str,
                 module_type: str,
                 **kwargs):
        super().__init__(*args, logger_name='DataBroker.capture_proc', **kwargs)
        LoggerMixin.configure_logger(level=os.getenv('LOGLEVEL'))
        self.shutdown_ev = shutdown_ev
        self.process_ready_event = process_ready_event
        self.data_capture_queue = data_capture_queue
        self.config_capture_queue = config_capture_queue
        self.module_name = module_name
        self.module_type = module_type

    def run(self):
        self.logger.info('started capturing process for %s', self.module_name)

        signal.signal(signal.SIGINT, lambda signum, frame: (self.shutdown_ev.set(),
                                                            log_reentrant(f'signal {signum} called')))
        signal.signal(signal.SIGTERM, lambda signum, frame: (self.shutdown_ev.set(),
                                                             log_reentrant(f'signal {signum} called')))

        thread_capture_kill_ev = threading.Event()
        thread_capture: Optional[threading.Thread] = None

        # signal that process is ready
        self.process_ready_event.set()

        # handle command queue
        while not self.shutdown_ev.is_set():
            try:
                try:
                    cap_cmd: CaptureCommand = self.config_capture_queue.get(timeout=0.2)
                except queue.Empty:
                    continue  # no data - check event and try again

                self.logger.debug('got command %s', cap_cmd)

                if cap_cmd.cmd == CaptureCommand.Command.STOP:
                    self.logger.info('processing STOP')
                    thread_capture_kill_ev.set()
                    if thread_capture is not None:
                        thread_capture.join()
                        thread_capture = None
                elif cap_cmd.cmd == CaptureCommand.Command.START:
                    self.logger.info('processing START')
                    assert thread_capture is None
                    thread_capture = threading.Thread(target=self._capture_thread, name='capture_thread',
                                                      args=[thread_capture_kill_ev,
                                                            cap_cmd.measurement_name,
                                                            cap_cmd.measurement_dir,
                                                            cap_cmd.module_data_schemas])
                    thread_capture_kill_ev.clear()
                    thread_capture.start()
                else:
                    raise ValueError(f'unknown command: {cap_cmd.cmd.name}')

                self.logger.debug('processed command: %s', cap_cmd.cmd.name)
            except Exception as e:
                self.logger.error(f'EX cap-command {type(e).__name__}: {e}\n{traceback.format_exc()}')

        self.logger.info('cleaning up')
        thread_capture_kill_ev.set()
        if thread_capture is not None:
            thread_capture.join()

        self.process_ready_event.clear()
        for q in [self.data_capture_queue, self.config_capture_queue]:
            empty_queue(q)
            q.close()

        self.logger.info('finished capturing process for %s', self.module_name)
        self.logger.debug(check_leftover_threads())

    def _capture_thread(self, thread_capture_kill_ev: threading.Event, measurement_name: str, measurement_dir: Path,
                        module_data_schemas: List):
        cap_logger = logging.getLogger('DataBroker.capture_thread')
        cap_logger.info('starting thread for %s', measurement_name)
        try:
            # make sure directory exists
            create_directory(Path(measurement_dir))
            # save as ".partXXXX.mcap" file and move when done
            temp_filename_ts = time.time_ns()
            temp_filename = f'{self.module_name}.part{temp_filename_ts}.mcap'
            mcap_file = open(measurement_dir / temp_filename, 'wb')
            json_channel_ids = []

            writer = McapWriter(mcap_file, compression=CompressionType.ZSTD, use_chunking=True)
            writer.start()
            # create a schema for each in list
            for idx, s in enumerate(module_data_schemas):
                new_schema = writer.register_schema(
                    name=f'{self.module_type}_{idx}' if 'dtype_name' not in s else s['dtype_name'],
                    encoding='jsonschema',
                    data=orjson.dumps(s))
                cap_logger.info(f'new schema: {new_schema} with topic: '
                                f'{self.module_type if "topic" not in s else s["topic"]}')
                json_channel_ids.append(writer.register_channel(
                    schema_id=new_schema,
                    topic=self.module_name if 'topic' not in s else s['topic'],
                    message_encoding='json',
                ))
        except Exception as _e:
            cap_logger.error(f'EX thread setup {type(_e).__name__}: {_e}\n{traceback.format_exc()}')
            return

        # signal parent, that we are ready
        self.process_ready_event.set()

        while not thread_capture_kill_ev.is_set():
            try:
                try:
                    raw = self.data_capture_queue.get(timeout=0.2)
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
                    data_json = orjson.dumps(data)
                    writer.add_message(
                        channel_id=json_channel_ids[schema_idx],
                        data=data_json,  # NaN not supported, null is OK
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
        if Path(measurement_dir / f'{self.module_name}.mcap').exists():
            cap_logger.warning('finished MCAP file already exists: %s.mcap', self.module_name)
            os.rename(measurement_dir / temp_filename, measurement_dir / f'{self.module_name}.{temp_filename_ts}.mcap')
        else:
            os.rename(measurement_dir / temp_filename, measurement_dir / f'{self.module_name}.mcap')
        cap_logger.info('finished capturing thread for %s', measurement_name)


class DataCaptureWorker(LoggerMixin):
    def __init__(self, *args, module_name: str, module_type: str, child_shutdown_ev: multiprocessing.Event,
                 data_dir: Path, **kwargs):
        super().__init__(*args, **kwargs)

        self.module_name: str = module_name
        self.module_type: str = module_type
        self.data_dir: Path = data_dir
        self._child_shutdown_ev: multiprocessing.Event = child_shutdown_ev

        # create capturing process
        self._capturing_active = False
        self._capture_queue: multiprocessing.Queue[Tuple[int, Dict, int]] = multiprocessing.Queue(maxsize=100000)
        self._capture_config_queue: multiprocessing.Queue[CaptureCommand] = multiprocessing.Queue(maxsize=4)
        self._capture_process_ready_event = multiprocessing.Event()
        self._capture_proc = CaptureProcess(shutdown_ev=child_shutdown_ev,
                                            process_ready_event=self._capture_process_ready_event,
                                            data_capture_queue=self._capture_queue,
                                            config_capture_queue=self._capture_config_queue,
                                            module_name=self.module_name,
                                            module_type=self.module_type)

    def get_module_data_dir(self, measurement_name: str) -> Path:
        return self.data_dir / measurement_name / self.module_name

    def start_process(self):
        self.logger.info('starting capture process')
        self._capture_proc.start()
        # wait for process to start
        self._capture_process_ready_event.wait(timeout=6)  # this should take about 0.5 seconds max.
        if self._capture_process_ready_event.is_set():
            self.logger.info('starting capture process succeeded')
        else:
            raise RuntimeError('starting capture process failed (timeout)')
        self._capture_process_ready_event.clear()

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
        empty_queue(self._capture_queue)
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

    def toggle_active(self, active: bool):
        self._capturing_active = active

    def is_active(self) -> bool:
        return self._capturing_active

    def capture_data(self, time_ns: int, schema_index: int, data: Dict):
        try:
            self._capture_queue.put_nowait((time_ns, data, schema_index))
        except Exception as e:
            self.logger.error(f'EX data_in capture {type(e).__name__}: {e}')

    def close(self):
        # clear multiprocessing queues (or a thread will remain after exit)
        self.logger.debug('emptying queues')
        for q in [self._capture_queue, self._capture_config_queue]:
            # _empty_queue(q) # ?? do not empty from this side
            q.close()

        if self._capture_proc is not None:
            if self._capture_proc.is_alive():
                self.logger.debug('joining capture process')
                self._capture_proc.join()
                self.logger.debug('joined capture process')
            self._capture_proc.close()

        self.logger.info('close data capture worker succeeded')