from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory


class DatabaseSyncConfig(BaseConfig):
    Name = 'system'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()

        cfg.string('button_start', "Start Sync").label("Start Sync").button()
        cfg.string('button_stop', "Stop Sync").label("Stop Sync").button()
        cfg.string('button_resync', "Force Re-Sync").label("Force Re-Sync").button()

        cfg.boolean('sync_on_capture_stop', False)

        cfg.integer('delay_before_start_s', 1).label("Delay before start [s]")

        cfg.string('db_host_port', 'timescaledb:5432')
        cfg.string('db_user', 'tsdb')
        cfg.string('db_password', 'tsdb123')
        cfg.string('db_name', 'metrics')

        cfg.string_array('sync_modules', ['ShellyPro3EM']).resizeable()

        return cfg.get_config()
