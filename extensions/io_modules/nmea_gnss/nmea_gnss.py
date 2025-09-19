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
from vif.data_interface.module_meta_factory import ModuleMetaFactory
from vif.data_interface.network_messages import Status

from io_modules.nmea_gnss.config import NMEAReaderConfig
from io_modules.nmea_gnss.ntrip_client import NTRIPClient



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

        self._ntrip_client: Optional[NTRIPClient] = None
        self._ntrip_com_channel_lock = threading.Lock()
        self._ntrip_com_channel = None

    def stop(self):
        self._stop_thread()
        self.logger.info('module closed')

    def _ntrip_cb_serial(self, data: bytes):
        with self._ntrip_com_channel_lock:
            if self._ntrip_com_channel:
                self._ntrip_com_channel.write(data)

    def _ntrip_cb_tcp(self, data: bytes):
        with self._ntrip_com_channel_lock:
            if self._ntrip_com_channel:
                self._ntrip_com_channel.sendall(data)

    def _worker_thread_fn(self):
        self.logger.debug('worker thread running')
        self.module_interface.set_ready_state(False)

        def _connect_tcp():
            _stream = None
            while not self._thread_stop_event.is_set():
                try:
                    _stream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    _stream.settimeout(1)
                    # _stream.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    _stream.connect((self.config_handler.config['hostname'], self.config_handler.config['tcp_port']))
                    self.logger.info('TCP/IP connected')
                    break
                except TimeoutError:
                    self.logger.debug('TCP/IP connect timeout')
                    continue
                except ConnectionRefusedError:
                    self.logger.debug('TCP/IP connect refused')
                    self._thread_stop_event.wait(1)
                    continue
            return _stream

        def _connect_serial():
            _stream = None
            while not self._thread_stop_event.is_set():
                try:
                    _stream = serial.Serial(self.config_handler.config['serial_port'],
                                            self.config_handler.config['serial_baudrate'], timeout=1)
                    self.logger.info('serial connected')
                    break
                except Exception as _e:
                    self.logger.error(f'EX connect serial {type(_e).__name__}: {_e}')
                    self._thread_stop_event.wait(1)
            return _stream

        stream: Optional[Union[socket.socket, serial.Serial]] = None

        if self.config_handler.config['input_mode'] == 'serial':
            stream = _connect_serial()
            with self._ntrip_com_channel_lock:
                self._ntrip_com_channel = stream
        elif self.config_handler.config['input_mode'] == 'TCP/IP':
            stream = _connect_tcp()
            with self._ntrip_com_channel_lock:
                self._ntrip_com_channel = _connect_tcp()
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
        self.module_interface.set_ready_state(True)
        send_gga_interval_s = self.config_handler.config['ntrip_vrs_gga_sending_interval_s']

        while not self._thread_stop_event.is_set():
            try:
                try:
                    (raw_data, parsed_data) = nmr.read()
                except serial.SerialException:
                    raw_data = None
                    parsed_data = None
                except Exception as e:
                    self.logger.error(f'EX NMEA read {type(e).__name__}: {e}')
                    continue

                time_rx = time.time_ns()

                # handle errors and reconnect
                if parsed_data is None:
                    self.module_interface.set_ready_state(False)
                    self.logger.error('NMEA read error: %s, %s', raw_data, parsed_data)
                    # timeout
                    if self.config_handler.config['input_mode'] == 'TCP/IP':
                        try:
                            _dummy = stream.recv(2, socket.MSG_DONTWAIT | socket.MSG_PEEK)
                            if len(_dummy) == 0:
                                continue
                        except TimeoutError:
                            continue  # ignore timeouts if GNSS does not send data
                        except Exception as e:
                            self.logger.error(f'EX worker {type(e).__name__}: {e}')
                            stream = _connect_tcp()
                            with self._ntrip_com_channel_lock:
                                self._ntrip_com_channel = _connect_tcp()
                    elif self.config_handler.config['input_mode'] == 'serial':
                        try:
                            _dummy = stream.read(2)
                            if len(_dummy) == 0:
                                continue
                        except Exception as e:
                            self.logger.error(f'EX worker {type(e).__name__}: {e}')
                            stream = _connect_serial()
                            with self._ntrip_com_channel_lock:
                                self._ntrip_com_channel = stream
                    else:
                        self.logger.error('worker: invalid config')
                        return

                    nmr = pynmeagps.NMEAReader(stream)
                    continue

                # self.logger.debug('%s', parsed_data)
                self.module_interface.set_ready_state(True)

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
                elif parsed_data.msgID == 'ASHR':  # orientation
                    try:
                        data['roll'] = float(parsed_data.roll)
                        data['pitch'] = float(parsed_data.pitch)
                        if 'heading' not in data:
                            data['heading'] = float(parsed_data.trueHdg)
                        data['imuAlign'] = parsed_data.imuAlign  # int
                    except ValueError:
                        if 'roll' in data:
                            data.pop('roll')
                        if 'pitch' in data:
                            data.pop('pitch')
                        if 'imuAlign' in data:
                            data.pop('imuAlign')
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
                    data['lat'] = parsed_data.lat if isinstance(parsed_data.lat, (int, float)) else None
                    data['lon'] = parsed_data.lon if isinstance(parsed_data.lon, (int, float)) else None
                    data['alt'] = parsed_data.alt if isinstance(parsed_data.alt, (int, float)) else None
                    data['numSV'] = parsed_data.numSV if isinstance(parsed_data.numSV, (int, float)) else None
                    data['quality'] = parsed_data.quality if isinstance(parsed_data.quality, (int, float)) else None
                    self.data_broker.data_in(time_rx, data, schema_index=0)

                    # second topic for GeoJSON (no live data)
                    if 'lat' in data and 'lon' in data and all([data['lat'], data['lon']]):
                        self.data_broker.data_in(time_rx, {'geojson': json.dumps(
                            {'type': 'Point', 'coordinates': [data['lon'], data['lat']]}
                        )}, schema_index=1, mcap=True, live=False, latest=False)

                    if self._ntrip_client and send_gga_interval_s >= 0:
                        data_ntrip = data.copy()
                        data_ntrip['sep'] = parsed_data.sep
                        data_ntrip['sip'] = parsed_data.numSV
                        data_ntrip['fix'] = pynmeagps.FIXTYPE_GGA[parsed_data.quality]
                        data_ntrip['hdop'] = parsed_data.HDOP
                        data_ntrip['diffage'] = parsed_data.diffAge
                        data_ntrip['diffstation'] = parsed_data.diffStation
                        self._ntrip_client.update_gga_info(data_ntrip)

            except Exception as e:
                self.logger.error(f'Exception in worker: {type(e).__name__}: {e}\n{traceback.format_exc()}')

        with self._ntrip_com_channel_lock:
            if isinstance(self._ntrip_com_channel, socket.socket):
                self._ntrip_com_channel.close()
            self._ntrip_com_channel = None
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

        if self._ntrip_client:
            self._ntrip_client.start_receive()

        if locking:
            self._thread_handling_lock.release()

    def _stop_thread(self, locking=True):
        if locking:
            self._thread_handling_lock.acquire()

        if self._worker_thread:
            self._thread_stop_event.set()
            self._worker_thread.join()
            self._worker_thread = None

        if self._ntrip_client:
            self._ntrip_client.stop_receive()

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

                with self._ntrip_com_channel_lock:
                    self._ntrip_com_channel = None
                if config['ntrip_client']:
                    self._ntrip_client = NTRIPClient(server=config['ntrip_server'],
                                                     port=config['ntrip_port'],
                                                     mountpoint=config['ntrip_mountpoint'],
                                                     user=config['ntrip_user'],
                                                     password=config['ntrip_password'],
                                                     send_gga_interval_s=config['ntrip_vrs_gga_sending_interval_s'],
                                                     timeout_s=config['ntrip_timeout'])
                    if self.config_handler.config['input_mode'] == 'TCP/IP':
                        self._ntrip_client.add_msg_callback(self._ntrip_cb_tcp)
                    elif self.config_handler.config['input_mode'] == 'serial':
                        self._ntrip_client.add_msg_callback(self._ntrip_cb_serial)
                else:
                    if self._ntrip_client:
                        self._ntrip_client.stop_receive()
                    self._ntrip_client = None

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

    def command_get_meta_data(self) -> ModuleMetaFactory:
        meta = ModuleMetaFactory()

        meta.add_dict({
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
        })

        return meta

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
