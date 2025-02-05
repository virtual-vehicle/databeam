from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory

class SystemMonitorConfig(BaseConfig):

    Name = 'system_monitor'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.number('update_interval_seconds', 60)
        cfg.string_array('disk_directories', ['/']).resizeable()

        return cfg.get_config()
