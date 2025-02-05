from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory

class ConstantPublisherConfig(BaseConfig):

    Name = 'constant_publisher'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.string_array('strings', ['Key1#My String']).resizeable()
        cfg.string_array('floats', ['Key2#1.23']).resizeable()
        cfg.string_array('integers', ['Key3#123']).resizeable()
        cfg.number('sleep_seconds', 1)

        return cfg.get_config()
