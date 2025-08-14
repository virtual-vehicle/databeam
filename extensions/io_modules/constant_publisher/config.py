from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory

class ConstantPublisherConfig(BaseConfig):

    Name = 'constant_publisher'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.string_array('strings', ['String1=My String']).resizeable()
        cfg.string_array('floats', ['Float1=1.23']).resizeable()
        cfg.string_array('integers', ['Int1=123']).resizeable()
        cfg.string_array('random_floats', ['Random1=5.0']).resizeable()
        cfg.number('random_deviation', 0.5)
        cfg.number('sleep_seconds', 1)

        return cfg.get_config()
