from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory


class StartstopForwarderConfig(BaseConfig):

    Name = 'system'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()

        cfg.string_array('follower_db_ids', ['dbid2']).resizeable().label('DB-IDs of Followers')

        return cfg.get_config()
