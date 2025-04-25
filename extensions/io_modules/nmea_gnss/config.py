from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory

class NMEAReaderConfig(BaseConfig):

    Name = 'nmea_gnss'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.string('input_mode', 'TCP/IP').select(['TCP/IP', 'serial'])
        cfg.string('hostname', '192.168.3.1')
        cfg.integer('tcp_port', 10110)
        cfg.string('serial_port', '/dev/serial/by-id/usb-u-blox_AG_-_www.u-blox.com_u-blox_GNSS_receiver-if00')
        cfg.integer('serial_baudrate', 460800)

        cfg.boolean('ntrip_client', False)
        cfg.integer('ntrip_vrs_gga_sending_interval_s', -1).visible('ntrip_client', True).indent()
        cfg.string('ntrip_server', 'www.euref-ip.net').visible('ntrip_client', True).indent()
        cfg.integer('ntrip_port', 2101).visible('ntrip_client', True).indent()
        cfg.string('ntrip_mountpoint', 'GRAZ00AUT0').visible('ntrip_client', True).indent()
        cfg.string('ntrip_user', 'user').visible('ntrip_client', True).indent()
        cfg.string('ntrip_password', 'password').visible('ntrip_client', True).indent()
        cfg.integer('ntrip_timeout', 10).visible('ntrip_client', True).indent()

        return cfg.get_config()
