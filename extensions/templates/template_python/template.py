"""
Template for IO-Module
Please consult libs/python/vif/data_interface/io_module.py for callback / base-class documentation
"""
import threading
import traceback
from typing import Optional, Dict, Union, List
import time

import environ

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.asyncio_helpers.asyncio_helpers import tick_generator
from vif.data_interface.network_messages import Status, IOEvent

from io_modules.template.config import TemplateConfig  # TODO adopt import path and name


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='Template')  # TODO adopt module name
    # TODO define any needed environment variables here


class Template(IOModule):  # TODO adopt module name
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME

        # worker thread starting and stopping is locked to avoid race condition during apply config vs. prepare sampling
        self._thread_handling_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        # worker thread stops when this event is set
        self._thread_stop_event = threading.Event()

    def start(self):
        self.logger.debug('starting')

    def stop(self):
        self._stop_thread()
        self.logger.info('module closed')

    def _worker_thread_fn(self):
        self.logger.debug('worker thread running')

        # Example for running something periodically. A real task may block on a physical resource.
        g = tick_generator(period_s=1, drop_missed=True, time_source=time.time)
        try:
            while not self._thread_stop_event.is_set():
                # data should be represented in a flat dict with channels described in command_get_schemas
                data = {'foo': 1}
                # timestamp is recorded in nanoseconds UTC
                time_rx = time.time_ns()
                self.logger.debug('%s', data)

                # hand over data to DataBeam internal system
                self.data_broker.data_in(time_rx, data)

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

    def command_validate_config(self, config: Dict) -> Status:
        # TODO do meaningful validation of config values / ranges
        return Status(error=False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            # make sure thread re-spawn is not intercepted by command_prepare_sampling
            with self._thread_handling_lock:
                self._stop_thread(locking=False)

                # TODO apply config values

                if self.module_interface.sampling_active() or self.module_interface.capturing_active():
                    self._start_thread(locking=False)

            return Status(error=False)

        except Exception as e:
            self.logger.error(f'error applying config: {type(e).__name__}: {e}\n{traceback.format_exc()}')
            return Status(error=True, title=type(e).__name__, message=str(e))

    def command_prepare_sampling(self):
        self.logger.info('prepare sampling!')
        self._start_thread()

    def command_start_sampling(self):
        self.logger.info('start sampling!')

    def command_stop_sampling(self):
        self.logger.info('stop sampling!')
        self._stop_thread()

    def command_prepare_capturing(self) -> None:
        pass

    def command_start_capturing(self) -> None:
        pass

    def command_stop_capturing(self) -> None:
        pass

    def command_get_meta_data(self) -> Dict[str, Union[str, int, float, bool]]:
        return {}

    def command_get_schemas(self) -> List[Dict]:
        return [{
            'type': 'object',
            'properties': {
                # TODO list all possible channel names and data types ('number', 'integer', 'string')
                # 'my_channel': {'type': 'number'}
            }
        }]

    def event_received(self, io_event: IOEvent) -> None:
        self.logger.debug('event received: %s', io_event.json_data)

    # unused class methods may be deleted - see io_module.py for default implementations


if __name__ == '__main__':
    main(Template, TemplateConfig, environ.to_config(ModuleEnv).MODULE_NAME)  # TODO adopt module name and config class
