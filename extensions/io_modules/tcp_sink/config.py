from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory

class TcpSinkConfig(BaseConfig):

    Name = 'tcp_sink'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.string('tcp_address', '0.0.0.0')
        cfg.integer('tcp_port', 2500).label('TCP Port (bind)')
        cfg.boolean('client_mode', True)
        cfg.boolean('use_length_bytes', False)
        cfg.number('number_length_bytes', 4)
        cfg.boolean('big_endian', False)
        cfg.string('data_format', 'struct').select(['struct', 'json'])
        cfg.string_array('struct_entries', ['key#f']).resizeable()

        return cfg.get_config()
