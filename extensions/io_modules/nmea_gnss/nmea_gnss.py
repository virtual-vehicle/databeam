"""
NMEA GNSS reader
"""
import json
import threading
import traceback
from typing import Optional, Dict, Union, List
import time
import serial
import socket

import environ
import pynmeagps

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule

from io_modules.nmea_gnss.config import NMEAReaderConfig

from vif.data_interface.network_messages import Status


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='NMEA_GNSS')


class NMEAReader(IOModule):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME

        self._thread_handling_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._thread_stop_event = threading.Event()

    def stop(self):
        self._stop_thread()
        self.logger.info('module closed')

    def _worker_thread_fn(self):
        self.logger.debug('worker thread running')

        def _connect_tcp():
            _stream = None
            while not self._thread_stop_event.is_set():
                try:
                    _stream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    _stream.settimeout(3)
                    # _stream.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    _stream.connect((self.config_handler.config['hostname'], self.config_handler.config['tcp_port']))
                    self.logger.info('TCP/IP connected')
                    break
                except TimeoutError:
                    self.logger.debug('TCP/IP connect timeout')
                    continue
            return _stream

        stream: Optional[Union[socket.socket, serial.Serial]] = None

        if self.config_handler.config['input_mode'] == 'serial':
            stream = serial.Serial(self.config_handler.config['serial_port'],
                                   self.config_handler.config['serial_baudrate'], timeout=1)
        elif self.config_handler.config['input_mode'] == 'TCP/IP':
            stream = _connect_tcp()
        else:
            self.logger.error('worker: invalid config')
            return

        nmr = pynmeagps.NMEAReader(stream)

        # keep latest data from different messages in a dict
        data = {}

        # THSLookup = {
        #     'A': 'autonomous',
        #     'E': 'estimated',
        #     'M': 'manual',
        #     'S': 'simulated',
        #     'V': 'invalid'
        # }

        try:
            while not self._thread_stop_event.is_set():
                (raw_data, parsed_data) = nmr.read()
                time_rx = time.time_ns()

                # handle errors and reconnect
                if parsed_data is None:
                    # timeout
                    if self.config_handler.config['input_mode'] == 'TCP/IP':
                        try:
                            _dummy = stream.recv(2, socket.MSG_DONTWAIT | socket.MSG_PEEK)
                            if len(_dummy) == 0:
                                continue
                        except Exception as e:
                            self.logger.error(f'EX worker {type(e).__name__}: {e}')
                            stream = _connect_tcp()
                            nmr = pynmeagps.NMEAReader(stream)
                    # TODO handle serial reconnect
                    continue

                # self.logger.debug('%s', parsed_data)

                if parsed_data.msgID == 'THS':  # for heading
                    try:
                        # true heading, same data as HDT message but with status
                        data['heading'] = float(parsed_data.headt)
                        data['heading_status'] = parsed_data.mi
                    except ValueError:
                        if 'heading' in data:
                            data.pop('heading')
                        if 'heading_status' in data:
                            data.pop('heading_status')
                elif parsed_data.msgID == 'VTG':  # for speed
                    # Septentrio: only arrives if IMU is fully aligned
                    try:
                        # speed over ground kmph --> convert to m/s
                        data['speed'] = float(parsed_data.sogk) / 3.6
                        # note: cogt (course over ground, true) does not match heading reported by THS, HDT
                    except ValueError:
                        if 'speed' in data:
                            data.pop('speed')
                elif parsed_data.msgID == 'GGA':
                    data['lat'] = parsed_data.lat
                    data['lon'] = parsed_data.lon
                    data['alt'] = parsed_data.alt
                    data['numSV'] = parsed_data.numSV
                    data['quality'] = parsed_data.quality
                    self.data_broker.data_in(time_rx, data, schema_index=0)

                    # second topic for GeoJSON (no live data)
                    if 'lat' in data and 'lon' in data:
                        self.data_broker.data_in(time_rx, {'geojson': json.dumps(
                            {'type': 'Point', 'coordinates': [data['lon'], data['lat']]}
                        )}, schema_index=1, mcap=True, live=False, latest=False)

        except Exception as e:
            self.logger.error(f'Exception in worker: {type(e).__name__}: {e}\n{traceback.format_exc()}')

        if stream is not None:
            self.logger.debug('closing port')
            stream.close()

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
        if 'input_mode' not in config or config['input_mode'] not in ['serial', 'TCP/IP']:
            return Status(error=True, title='invalid config', message='invalid input_mode')

        if 'hostname' not in config:
            return Status(error=True, title='invalid config', message='invalid hostname')
        if 'tcp_port' not in config or not (1024 <= config['tcp_port'] <= 49151):
            return Status(error=True, title='invalid config', message='invalid tcp_port')

        if 'serial_port' not in config:
            return Status(error=True, title='invalid config', message='invalid serial_port')
        if 'serial_baudrate' not in config:
            return Status(error=True, title='invalid config', message='invalid serial_baudrate')

        # TODO other config validations

        return Status(error=False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            # make sure thread re-spawn is not intercepted
            with self._thread_handling_lock:
                self._stop_thread(locking=False)

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
        return {
            'lat': 'deg',
            'lon': 'deg',
            'alt': 'm',
            'numSV': 'int',
            # https://github.com/adrianmo/go-nmea/blob/master/gga.go
            'quality': '{0: "invalid", 1: "GPS", 2: "DGPS", 3: "PPS", 4: "RTK fixed", 5: "RTK float", 6: "estimated"}',
            'heading': 'deg',
            # https://github.com/adrianmo/go-nmea/blob/master/ths.go
            'heading_status': '{"A": "autonomous", "E": "estimated", "M": "manual", "S": "simulated", "V": "invalid"}',
            'speed': 'm/s',
        }

    def command_get_schemas(self) -> List[Dict]:
        return [{
            'type': 'object',
            'properties': {
                'lat': {'type': 'number'},
                'lon': {'type': 'number'},
                'alt': {'type': 'number'},
                'numSV': {'type': 'integer'},
                'quality': {'type': 'integer'},
                'heading': {'type': 'number'},
                'heading_status': {'type': 'string'},  # TODO use bool: valid/invalid ??
                'speed': {'type': 'number'}
            }
        }, {
            'topic': f'{self.module_interface.data_broker.replace_name_chars(self.config_handler.type)}_GeoJSON',
            'dtype_name': 'foxglove.GeoJSON',
            "description": "GeoJSON data for annotating maps",
            "$comment": "Generated by https://github.com/foxglove/schemas",
            'type': 'object',
            'properties': {
                'geojson': {
                    "type": "string",
                    "description": "GeoJSON data encoded as a UTF-8 string"
                }
            }
        }]


if __name__ == '__main__':
    main(NMEAReader, NMEAReaderConfig, environ.to_config(ModuleEnv).MODULE_NAME)
