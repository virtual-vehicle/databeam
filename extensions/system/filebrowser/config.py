from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory


class FileBrowserConfig(BaseConfig):  # TODO adopt config name

    # TODO replace with proper name/type of config (use lower_case)
    Name = 'filebrowser'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()

        cfg.number("port", 8044)
        cfg.string("username", "databeam")
        cfg.string("password", "default")
        cfg.boolean("allow_delete_data", False)

        return cfg.get_config()
