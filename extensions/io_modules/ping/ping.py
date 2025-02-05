"""
Ping Receiver and Parser
"""
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError, CancelledError
from typing import Optional, List, Dict
import time

import environ
import pingparsing

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.asyncio_helpers.asyncio_helpers import tick_generator

from io_modules.ping.config import PingConfig

from vif.data_interface.network_messages import Status


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='Ping')


class Ping(IOModule):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME

        self._thread_handling_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._thread_stop_event = threading.Event()

        self._executor: Optional[ThreadPoolExecutor] = None

        self._transmitters: List[pingparsing.PingTransmitter] = []
        self._timeout_s = 500
        self._interval_s = 1000

    def stop(self):
        self._stop_thread()
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=True)
        self.logger.info('module closed')

    def _worker_thread_fn(self):
        self.logger.debug('worker thread running')
        if len(self._transmitters) == 0:
            self.logger.warning('no servers configured - closing thread')
            return
        self._executor = ThreadPoolExecutor(max_workers=len(self._transmitters), thread_name_prefix='ping')
        ping_parser = pingparsing.PingParsing()
        g = tick_generator(self._interval_s, drop_missed=True, time_source=time.time)
        try:
            while not self._thread_stop_event.is_set():
                if len(self._transmitters):
                    t_start = time.time()
                    results = {k.destination: -1.0 for k in self._transmitters}
                    pings = [self._executor.submit(t.ping) for t in self._transmitters]
                    time_ping_executed = time.time_ns()
                    for ping in pings:
                        if self._thread_stop_event.is_set():
                            ping.cancel()  # cancel all future tasks if we need to shut down
                        try:
                            parsed = ping_parser.parse(ping.result(timeout=self._timeout_s))
                            data = parsed.rtt_avg
                        except (TimeoutError, CancelledError):
                            ping.cancel()
                        except Exception as exc:
                            self.logger.error(f'Exception: {type(exc).__name__} {exc}')
                        else:
                            # do not save "None" values -> keep invalid as "-1"
                            if data is not None:
                                results[parsed.destination] = data

                    if not self._thread_stop_event.is_set():
                        # self.logger.debug('%.2fs %s', time.time() - t_start, results)
                        self.data_broker.data_in(time_ping_executed, results)

                # wait for timeout or killed thread
                self._thread_stop_event.wait(timeout=next(g))
        except Exception as e:
            self.logger.error(f'Exception in worker: {type(e).__name__}: {e}\n{traceback.format_exc()}')
        g.close()
        self.logger.debug('thread gone')

    def _start_thread(self, locking=True):
        if locking:
            self._thread_handling_lock.acquire()

        if self._worker_thread and self._worker_thread.is_alive():
            self.logger.warning('_start_thread: thread already running')
        else:
            self._worker_thread = threading.Thread(target=self._worker_thread_fn, name='worker')
            self._thread_stop_event.clear()
            self._worker_thread.start()

        if locking:
            self._thread_handling_lock.release()

    def _stop_thread(self, locking=True):
        if locking:
            self._thread_handling_lock.acquire()

        if self._worker_thread:
            self._thread_stop_event.set()
            self._worker_thread.join()
            self._worker_thread = None

        if locking:
            self._thread_handling_lock.release()

    def command_validate_config(self, config) -> Status:
        if config['ping_timeout_ms'] > 1000:
            return Status(error=True, title='invalid config', message='select a timeout not greater than 1000')

        if config['ping_timeout_ms'] >= config['ping_interval_ms']:
            return Status(error=True, title='invalid config', message='select a timeout smaller than interval')

        return Status(error=False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            # make sure thread re-spawn is not intercepted
            with self._thread_handling_lock:
                self._stop_thread(locking=False)

                self._transmitters = []
                for server in config['servers']:
                    transmitter = pingparsing.PingTransmitter()
                    transmitter.destination = server
                    transmitter.count = 1
                    transmitter.timeout = f"{int(config['ping_timeout_ms'])}ms"
                    self._transmitters.append(transmitter)

                self._interval_s = config['ping_interval_ms']/1000
                self._timeout_s = config['ping_timeout_ms']/1000

                if self.module_interface.sampling_active() or self.module_interface.capturing_active():
                    self._start_thread(locking=False)

            return Status(error=False)

        except Exception as e:
            self.logger.error(f'error applying config: {type(e).__name__}: {e}\n{traceback.format_exc()}')
            return Status(error=True, title=type(e).__name__, message=str(e))

    def command_prepare_sampling(self):
        self.logger.info('prepare sampling!')
        self._start_thread()

    def command_stop_sampling(self):
        self.logger.info('stop sampling!')
        self._stop_thread()

    def command_get_schemas(self) -> List[Dict]:
        return [{
            'type': 'object',
            'properties': {
                k.destination: {'type': 'number'} for k in self._transmitters
            }
        }]


if __name__ == '__main__':
    main(Ping, PingConfig, environ.to_config(ModuleEnv).MODULE_NAME)
