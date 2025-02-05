from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory

class GpsdClientConfig(BaseConfig):

    Name = 'gpsd_client'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.string('gpsd_hostname', '127.0.0.1')
        cfg.integer('port', 2947)

        return cfg.get_config()
