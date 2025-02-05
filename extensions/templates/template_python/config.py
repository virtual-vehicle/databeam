from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory


class TemplateConfig(BaseConfig):  # TODO adopt config name

    # TODO replace with proper name/type of config (use lower_case)
    Name = 'template'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()

        cfg.string('config_key', 'config_value').label('Config Key')

        return cfg.get_config()
