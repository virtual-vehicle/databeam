from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory


class FileBrowserConfig(BaseConfig):
    Name = 'filebrowser'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()

        cfg.number("port", 8044)
        cfg.string("username", "databeam")
        cfg.string("password", "default")
        cfg.boolean("allow_delete_data", False)
        cfg.boolean("use_single_click", True)

        return cfg.get_config()
