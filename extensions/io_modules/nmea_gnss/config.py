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
        cfg.string('serial_port', '/dev/ttyACM0')
        cfg.integer('serial_baudrate', 115200)

        return cfg.get_config()
