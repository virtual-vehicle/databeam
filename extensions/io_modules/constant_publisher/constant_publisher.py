"""
Constant Publisher
"""
import threading
import traceback
from typing import Optional, Dict, Union, List
import time

import environ

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.asyncio_helpers.asyncio_helpers import tick_generator

from io_modules.constant_publisher.config import ConstantPublisherConfig

from vif.data_interface.network_messages import Status


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='ConstantPublisher')


class ConstantPublisher(IOModule):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME

        self._thread_handling_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._thread_stop_event = threading.Event()

        self.constant_data = {}

    def stop(self):
        self._stop_thread()
        self.logger.info('module closed')

    def _worker_thread_fn(self):
        self.logger.debug('worker thread running')
        g = tick_generator(self.config_handler.config['sleep_seconds'], drop_missed=True, time_source=time.time)
        try:
            while not self._thread_stop_event.is_set():
                data = {}
                for d in self.constant_data.values():
                    for k, v in d.items():
                        data[k] = v
                self.data_broker.data_in(time.time_ns(), data)
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
        if config['sleep_seconds'] < 0.001:
            self.logger.error(f"config rejected: sleep value too small: {config['sleep_seconds']}")
            return Status(error=True, title='Invalid config', message=f'sleep value too small: '
                                                                      f'{config["sleep_seconds"]}')

        return Status(error=False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            def _add_value(_data, _key, _value):
                if _key in _data:
                    self.logger.warning(f"config warning: duplicated key: {_key} (value: {_value})")
                    # TODO self._data_interface.log_gui("Const-Pub Config", "Duplicated key!")
                _data[_key] = _value
                return _data

            # make sure thread re-spawn is not intercepted
            with self._thread_handling_lock:
                self._stop_thread(locking=False)

                try:
                    new_constant_data = {
                        'string': {},
                        'number': {},
                        'integer': {},
                    }
                    for s in config['strings']:
                        _add_value(new_constant_data['string'], *s.split('#'))
                    for f in config['floats']:
                        key, value = f.split('#')
                        _add_value(new_constant_data['number'], key, float(value))
                    for i in config['integers']:
                        key, value = i.split('#')
                        _add_value(new_constant_data['integer'], key, int(value))
                except Exception as e:
                    self.logger.error(f"config rejected: {type(e).__name__}: {e}")
                    # TODO self._data_interface.log_gui("Const-Pub Config Error", type(e).__name__)
                    return Status(error=True, title=type(e).__name__, message="Bad key or value!")

                # store updated values
                self.constant_data = new_constant_data
                self.logger.info(f"configured constant data: {self.constant_data}")

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

    def command_get_meta_data(self) -> Dict[str, Union[str, int, float, bool]]:
        meta = {}
        for d_type, x in self.constant_data.items():
            for k, v in x.items():
                meta[f'{k}_{d_type}'] = v
        return meta

    def command_get_schemas(self) -> List[Dict]:
        props = {}
        for d_type, x in self.constant_data.items():
            for k in x.keys():
                props[k] = {'type': d_type}
        return [{
            'type': 'object',
            'properties': props
        }]


if __name__ == '__main__':
    main(ConstantPublisher, ConstantPublisherConfig, environ.to_config(ModuleEnv).MODULE_NAME)
