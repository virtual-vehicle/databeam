import queue
import threading
import logging
import signal
import time
import traceback
from typing import List, Callable, Optional, Dict

import pynmeagps
import pygnssutils
from pygnssutils.gnssntripclient import GGALIVE, NOGGA

from vif.logger.logger import LoggerMixin, log_reentrant


_NTRIP_Callback = Callable[[bytes], None]


class NTRIPClient(LoggerMixin):
    """
    RTCM via IP client
    connects to a NTRIP 2.0 server and forwards all RTCM data to registered callback
    """

    def __init__(self, server: str, port: int, mountpoint: str, user: str, password: str, send_gga_interval_s: int,
                 timeout_s: int):
        """
        Creates the client without connecting to the server
        :param server: hostname to connect to
        :param port: port to connect to
        :param mountpoint: mountpoint / station name (e.g. 'GRAZ00AUT0')
        :param user: user for service authentication
        :param password: password for user
        :param send_gga_interval_s: enable sending of GGA messages for VRS: -1 = OFF ; >= 0 = send every n seconds
        :param timeout_s: timeout in seconds
        :raises KeyError: if a required config key is missing
        """
        super().__init__()

        self._shutdown_event = threading.Event()

        self._msg_callbacks: List[_NTRIP_Callback] = []
        self._worker_thread: Optional[threading.Thread] = None

        self._server = server
        self._port = port
        self._mountpoint = mountpoint
        self._user = user
        self._password = password
        self._send_gga_interval_s = send_gga_interval_s
        self._timeout = timeout_s

        self._latest_gga: Dict = {}

    def __del__(self):
        self.stop_receive()

    def add_msg_callback(self, msg_callback: _NTRIP_Callback) -> None:
        """
        Attach a function to be called when new RTCM data is received
        Multiple callback functions are supported
        :param msg_callback: function to be called
        """
        self._msg_callbacks.append(msg_callback)

    def remove_msg_callback(self, msg_callback: _NTRIP_Callback) -> None:
        """
        Removes a previously attached function
        :param msg_callback: the function to be removed
        :raises ValueError: if the function to be removed is not attached
        """
        self._msg_callbacks.remove(msg_callback)

    def start_receive(self) -> None:
        """
        Starts the Client
        """
        self.stop_receive()

        self._shutdown_event.clear()
        self._worker_thread = threading.Thread(target=self._run_socket_reader_lib, name='ntrip_socket_reader')
        self._worker_thread.start()

    def stop_receive(self) -> None:
        """
        Stops the client
        """
        self._shutdown_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join()
        self._worker_thread = None

    def update_gga_info(self, gga_message: Dict) -> None:
        # self.logger.debug(f'update GGA: {len(gga_message)} bytes: {gga_message}')
        self._latest_gga = gga_message

    def get_coordinates(self) -> Dict:
        """
        gets called by GNSSNTRIPClient to fetch latest GGA message
        :return: dict with coordinates and metadata --> library will do: lat = coords.get("lat", lat)
        """
        return self._latest_gga

    def _run_socket_reader_lib(self) -> None:
        self.logger.debug('start reader thread')

        gnc = None
        logging.getLogger("pygnssutils.gnssntripclient").setLevel(logging.WARNING)
        while not self._shutdown_event.is_set():
            try:
                outqueue = queue.Queue()

                gnc = pygnssutils.GNSSNTRIPClient(app=self, timeout=self._timeout)
                gnc.run(
                    server=self._server, port=self._port, https=0,
                    mountpoint=self._mountpoint,
                    datatype="RTCM",
                    ntripuser=self._user,
                    ntrippassword=self._password,
                    ggainterval=NOGGA if self._send_gga_interval_s < 0 else self._send_gga_interval_s,
                    ggamode=GGALIVE,
                    output=outqueue
                )
                self.logger.debug('start output processing')
                time_last_rx = time.time()
                while not self._shutdown_event.is_set():
                    try:
                        if time.time() - time_last_rx > self._timeout:
                            self.logger.error(f'no data received for {self._timeout} s')
                            break
                        raw, parsed = outqueue.get(timeout=0.2)
                        time_last_rx = time.time()
                        if isinstance(parsed, pynmeagps.nmeamessage.NMEAMessage):
                            # do not forward NMEA messages to receiver
                            outqueue.task_done()
                            continue
                        for cb in self._msg_callbacks:
                            cb(raw)
                        outqueue.task_done()
                    except queue.Empty:
                        pass

            except Exception as e:
                self.logger.error(f'EX in NTRIP receiver: {type(e).__name__}: {e}\n{traceback.format_exc()}')

            finally:
                if gnc:
                    self.logger.debug('stopping GNSSNTRIPClient')
                    gnc.stop()

        self.logger.info("NTRIP receiver stopped")


if __name__ == '__main__':
    LoggerMixin.configure_logger(level='DEBUG')
    logger = logging.getLogger('NTRIP')

    def sig_handler(signum, frame):
        logger.info(f'signal {signum} called')

    signal.signal(signal.SIGINT, lambda signum, frame: (log_reentrant(f'signal {signum} called')))
    signal.signal(signal.SIGTERM, sig_handler)

    def _print(data) -> None:
        print_data_raw = False
        print(f'got {len(data)}: {data if print_data_raw else "..."})')

    client = NTRIPClient(server='www.euref-ip.net', port=2101, mountpoint='GRAZ00AUT0',
                         user='user', password='pw', send_gga_interval_s=4, timeout_s=5)
    client.add_msg_callback(_print)
    client.start_receive()

    signal.pause()
    client.stop_receive()
