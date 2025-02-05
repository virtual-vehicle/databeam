from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory


class AutoStartConfig(BaseConfig):

    Name = 'autostart'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.boolean('capture_on_start_enabled', False)
        cfg.number('capture_on_start_delay_s', 5)
        cfg.boolean('capture_restart_enabled', False)
        cfg.string('capture_restart_time', '00:00:00')
        cfg.string('capture_restart_interval', 'Hour').select(['Day', 'Hour', 'Minute'])

        return cfg.get_config()
