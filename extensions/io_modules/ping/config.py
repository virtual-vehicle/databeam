import json
from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory

class PingConfig(BaseConfig):
    Name = 'ping'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.integer('ping_interval_ms', 1000).label('Interval [ms]')
        cfg.integer('ping_timeout_ms', 500).label('Timeout [ms]')
        cfg.string_array('servers', ['v2c2.at']).resizeable()
        cfg.string('button', "button").label("Hit That Button").button()
        return cfg.get_config()
