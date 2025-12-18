from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory


class AutostopConfig(BaseConfig):
    Name = 'autostop'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()

        cfg.boolean("enable_autostop", False)
        cfg.integer("measurement_duration", 60).label("Measurement Duration [sec]")

        return cfg.get_config()
