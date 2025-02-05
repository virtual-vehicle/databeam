from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory

class UdpSinkConfig(BaseConfig):

    Name = 'udp_sink'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.string('udp_address', '0.0.0.0')
        cfg.integer('udp_port', 2500).label('udp Port (bind)')
        cfg.boolean('use_length_bytes', False)
        cfg.number('number_length_bytes', 4)
        cfg.boolean('big_endian', False)
        cfg.string('data_format', 'struct').select(['struct', 'json'])
        cfg.string_array('struct_entries', ['key#f']).resizeable()

        return cfg.get_config()
