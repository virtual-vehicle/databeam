"""
Gpsd Client
"""
import json
import threading
import traceback
from typing import Optional, Dict, List
import time
import math
from datetime import datetime

import environ
from gpsdclient import GPSDClient

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule

from io_modules.gpsd_client.config import GpsdClientConfig

from vif.data_interface.network_messages import Status


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='GpsdClient')


class GpsdClient(IOModule):

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
        error_displayed = False

        while not self._thread_stop_event.is_set():
            try:
                with GPSDClient(host=self.config_handler.config['gpsd_hostname'],
                                port=self.config_handler.config['port']) as client:
                    for result in client.dict_stream(convert_datetime=True, filter=["TPV"]):
                        # sample current time
                        time_rx = time.time_ns()

                        # TODO test without filter and see what arrives.
                        # TODO parse all messages and combine with latest values (drop old values with timeout?)
                        # ATT message may have pitch, yaw, roll
                        # TODO verify lat/lon have high resolution!!

                        if self._thread_stop_event.is_set():
                            break

                        gps_time_s = result.get('time', datetime.fromtimestamp(0.0)).timestamp()
                        # calculate time offset in seconds
                        gps_time_offset_s = time_rx/1e9 - gps_time_s

                        # example of available fields (https://gpsd.gitlab.io/gpsd/gpsd_json.html):
                        """
                        class : TPV
                        device : /dev/serial/by-id/usb-u-blox_AG_-_www.u-blox.com_u-blox_GNSS_receiver-if00
                        mode : 3
                        time : 2023-03-29 13:54:06+00:00
                        ept : 0.005
                        lat : 47.0580905
                        lon : 15.462346667
                        altHAE : 430.9
                        altMSL : 388.5
                        alt : 388.5
                        epx : 9.078
                        epy : 8.677
                        epv : 33.35
                        magvar : 4.2
                        speed : 0.049
                        climb : 0.1
                        eps : 18.16
                        epc : 65.09
                        geoidSep : 42.4
                        eph : 17.48
                        sep : 32.68
                        """

                        data = {
                            'gTime': gps_time_s,
                            'gTimeOff': gps_time_offset_s,
                            'lat': result.get('lat', float('NaN')),
                            'lon': result.get('lon', float('NaN')),
                            'hMSL': result.get('altMSL', float('NaN')),
                            'gSpeed': result.get('speed', float('NaN')),
                            'headMot': result.get('track', float('NaN')),
                            'fixType': result.get('mode', 0),
                            'hAcc': result.get('eph', float('NaN')),
                            'vAcc': result.get('epv', float('NaN')),
                            'sAcc': result.get('eps', float('NaN')),
                            'headAcc': math.radians(result.get('epd', float('NaN'))),
                        }
                        # filter NaN values
                        data = {k: v for k, v in data.items() if not math.isnan(v)}
                        # self.logger.debug(f"Data: {data}")

                        # TODO specify reduced set for live data
                        self.data_broker.data_in(time_rx, data, schema_index=0)

                        # second topic for GeoJSON (no live data)
                        if 'lat' in data and 'lon' in data:
                            self.data_broker.data_in(time_rx, {'geojson': json.dumps({
                                'type': 'Point', 'coordinates': [data['lon'], data['lat']]}
                            )}, schema_index=1, mcap=True, live=False, latest=False)

            except ConnectionRefusedError:
                self.logger.error('ConnectionRefusedError: check gpsd and config!')
                if not error_displayed:
                    # indicate in UI that target file does not exist
                    self.module_interface.log_gui("Gpsd: connection refused. Check gpsd and config!")
                    error_displayed = True
                self._thread_stop_event.wait(5)
            except Exception as e:
                self.logger.error(f'Exception in worker: {type(e).__name__}: {e}\n{traceback.format_exc()}')
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

    def command_get_schemas(self) -> List[Dict]:
        return [{
            'type': 'object',
            'properties': {
                'gTime': {'type': 'number'},
                'gTimeOff': {'type': 'number'},
                'lat': {'type': 'number'},
                'lon': {'type': 'number'},
                'hMSL': {'type': 'number'},
                'gSpeed': {'type': 'number'},
                'headMot': {'type': 'number'},
                'fixType': {'type': 'integer'},
                'hAcc': {'type': 'number'},
                'vAcc': {'type': 'number'},
                'sAcc': {'type': 'number'},
                'headAcc': {'type': 'number'},
            }
        }, {
            'topic': f'{self.module_interface.data_broker.replace_name_chars(self.name)}_GeoJSON',
            'dtype_name': 'foxglove.GeoJSON',
            'type': 'object',
            'properties': {
                'geojson': {
                    "type": "string",
                    "description": "GeoJSON data encoded as a UTF-8 string"
                }
            }
        }]


if __name__ == '__main__':
    main(GpsdClient, GpsdClientConfig, environ.to_config(ModuleEnv).MODULE_NAME)
