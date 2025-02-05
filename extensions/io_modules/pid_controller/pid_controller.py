"""
PID Controller
"""
import math
import threading
import traceback
from typing import Optional, Dict, List
import time
from functools import partial

import environ

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.asyncio_helpers.asyncio_helpers import tick_generator

from io_modules.pid_controller.config import PIDControllerConfig

from io_modules.pid_controller.pid import PID

from vif.data_interface.network_messages import Status


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='PIDController')


class PIDController(IOModule):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME

        self._thread_handling_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._thread_stop_event = threading.Event()

        self._pid = PID()
        self._period_s = 1.0
        self._setpoint = 0.0
        self._input_value = None
        self._input_value_time = None

    def stop(self):
        self._stop_thread()
        self.logger.info('module closed')

    def _worker_thread_fn(self):
        self.logger.debug('worker thread running')

        self._pid.reset_state()

        g = tick_generator(self._period_s, drop_missed=True, time_source=time.time)
        try:
            while not self._thread_stop_event.is_set():
                # failsafe: if input value update is older than 2*TS: stop!
                if self._input_value is not None and self._input_value_time is not None:
                    age_sec = time.time() - self._input_value_time
                    if age_sec > self._period_s * 2:
                        self.logger.warning('input value too old: %.2f s', age_sec)
                        pid_output = (self.config_handler.config['output_min'], 0.0, 0.0, 0.0)
                        data = dict(zip(('output', 'p_share', 'i_share', 'd_share'), pid_output))
                        data['pv'] = self._input_value
                        self.data_broker.data_in(time.time_ns(), data)
                        self._input_value = None
                        continue

                if self._input_value is not None:
                    time_update = time.time_ns()
                    if self.config_handler.config['force_on']:
                        pid_output = (self.config_handler.config['output_max'], 0.0, 0.0, 0.0)
                        self._pid.reset_state()
                    elif (self.config_handler.config['input_valid_min'] <= self._input_value <=
                            self.config_handler.config['input_valid_max']):
                        # use PID only if input value is in valid range
                        pid_output = self._pid.update(pv=self._input_value, sp=self._setpoint)
                    else:
                        self.logger.warning('input value %.2f out of valid range: %.2f -> %.2f',
                                            self._input_value,
                                            self.config_handler.config['input_valid_min'],
                                            self.config_handler.config['input_valid_max'])
                        pid_output = (self.config_handler.config['output_min'], 0.0, 0.0, 0.0)
                        self._pid.reset_state()
                    data = dict(zip(('output', 'p_share', 'i_share', 'd_share'), pid_output))
                    data['pv'] = self._input_value
                    self.data_broker.data_in(time_update, data)
                else:
                    self.logger.debug('no input value')

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
        if len(config['input_module']) < 1:
            return Status(error=True, title='invalid config', message='no input module defined')
        if len(config['input_channel']) < 1:
            return Status(error=True, title='invalid config', message='no input channel defined')

        if config['output_min'] >= config['output_max']:
            return Status(error=True, title='invalid config', message='invalid output range')

        if config['input_valid_min'] >= config['input_valid_max']:
            return Status(error=True, title='invalid config', message='invalid valid input range')

        return Status(error=False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            # make sure thread re-spawn is not intercepted
            with self._thread_handling_lock:
                # do not stop thread if only parameters change
                if self._period_s != config['period_s']:
                    self._stop_thread(locking=False)
                    self._period_s = config['period_s']

                # PID parameters
                self._pid.change_limits(u_min=config['output_min'], u_max=config['output_max'], inverted=config['inverted'])
                self._pid.change_control_values(ts_s=config['period_s'], kp=config['k_p'], ki=config['k_i'],
                                                kd=config['k_d'])
                # setpoint / PID target
                self._setpoint = config['setpoint']

                # input subscriber
                self.module_interface.live_data_receiver.request_live_data(
                    [config['input_module']],
                    [True if config["input_sub_mode"] == "liveall" else False],
                    data_callback=partial(self._data_received, config['input_channel']))

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
                'output': {'type': 'number'},
                'p_share': {'type': 'number'},
                'i_share': {'type': 'number'},
                'd_share': {'type': 'number'},
                'pv': {'type': 'number'},
            }
        }]

    def _data_received(self, channel: str, db_id: str, module: str, data: Dict) -> None:
        # self.logger.debug('input data received: %s', data)
        try:
            if math.isnan(data[channel]):
                self.logger.warning('NaN data received: %s', data)
                return
            self._input_value_time = time.time()
            self._input_value = data[channel]
        except Exception as e:
            self.logger.error(f'EX data_received ({data}) - {type(e).__name__}: {e}')
            return


if __name__ == '__main__':
    main(PIDController, PIDControllerConfig, environ.to_config(ModuleEnv).MODULE_NAME)
