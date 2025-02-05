"""
Tcp Sink IO module.
"""
import struct
import threading
import traceback
from typing import Optional, Dict, Union, List
import time

import environ

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.data_interface.network_messages import Status, IOEvent

from io_modules.tcp_sink.config import TcpSinkConfig

from TcpManager import TcpManager, ErrorCode


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='TcpSink')


class TcpSink(IOModule):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME

        self._thread_handling_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._thread_stop_event = threading.Event()

        self.tcp_manager = TcpManager()

    def start(self):
        self.logger.debug('starting')

    def stop(self):
        self._stop_thread()
        self.tcp_manager.close()
        self.logger.info('module closed')

    def _worker_thread_fn(self):
        self.logger.debug('worker thread running')

        try:
            while not self._thread_stop_event.is_set():
                if self.tcp_manager.connect() != ErrorCode.OK:
                    continue

                while not self._thread_stop_event.is_set():
                    time_rx = time.time_ns()
                    error_code, data = self.tcp_manager.receive()

                    if error_code == ErrorCode.OK:
                        self.data_broker.data_in(time_rx, data)
                    elif error_code == ErrorCode.RECOVERABLE:
                        continue
                    elif error_code == ErrorCode.CRITICAL:
                        if not self._thread_stop_event.is_set():
                            self.logger.error("TCP connection broke during data receiving.")
                            self._config_and_restart_tcp_manager()
                            break

        except Exception as e:
            self.logger.error(f'Exception in worker: {type(e).__name__}: {e}\n{traceback.format_exc()}')
        self._config_and_restart_tcp_manager()
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
        if config["data_format"] != "json" and config["data_format"] != "struct":
            return Status(error=True, message="Data Format must be either json or struct.")
        return Status(error=False)

    def _config_and_restart_tcp_manager(self):
        """
        Closes the current tcp connection, if one exists, configures everything and directly listens to incoming
        connections. Can be used to listen to connections directly after config application and after restarting
        a measurement.
        """
        config = self.config_handler.config
        self.tcp_manager.close()
        self.tcp_manager.config(config, self._thread_stop_event)
        setup_success = self.tcp_manager.setup()
        if setup_success:
            self.logger.info("TCP socket set up for %s:%s",
                             config["tcp_address"], config["tcp_port"])
        else:
            self.logger.warning("TCP socket could not be set up for %s:%s",
                                config["tcp_address"], config["tcp_port"])

    def _parse_struct_definition(self, config):
        """
        Parses the struct config definition and passes them to the TcpManager. Incoming struct data is later
        interpreted with this definition.
        """
        if config["big_endian"]:
            struct_format = '>'
        else:
            struct_format = "<"
        struct_names = []
        try:
            for s in config['struct_entries']:
                entry = s.split('#')
                struct_names.append(entry[0])
                struct_format = f'{struct_format}{entry[1] if len(entry[1]) >= 1 else "_"}'
        except IndexError:
            return Status(True, message="Schema validation failed: struct entry not in format Name#Type")

        try:
            self.tcp_manager.struct_size = struct.calcsize(struct_format)
            self.tcp_manager.struct_format = struct_format
            self.tcp_manager.struct_names = struct_names
            self.logger.info(f"STRUCT SIZE = {self.tcp_manager.struct_size}")
        except struct.error as e:
            return Status(True, message=f'Schema validation failed: {e}\nsee: <a target="_blank" '
                                        f'href="https://docs.python.org/3/library/struct.html#format-characters">struct'
                                        f'format</a>')

        if self.module_interface.sampling_active() or self.module_interface.capturing_active():
            self._start_thread(locking=False)
        return Status(False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            # make sure thread re-spawn is not intercepted
            with self._thread_handling_lock:
                self._stop_thread(locking=False)

                self._config_and_restart_tcp_manager()
                status = self._parse_struct_definition(config)
                if status.error:
                    return status

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


if __name__ == '__main__':
    main(TcpSink, TcpSinkConfig, environ.to_config(ModuleEnv).MODULE_NAME)
