from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory

class PIDControllerConfig(BaseConfig):

    Name = 'pid'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.boolean('force_on', False)
        cfg.number('k_p', 1.0)
        cfg.number('k_i', 1.0)
        cfg.number('k_d', 0.0)
        cfg.number('period_s', 1.0)
        cfg.number('output_max', 100.0)
        cfg.number('output_min', 0.0)
        cfg.boolean('inverted', False)
        cfg.number('setpoint', 0.0)
        cfg.string('input_module', 'REDLAB_TEMP_1')
        cfg.string('input_channel', 'CH_0')
        cfg.string('input_sub_mode', 'liveall').select(['liveall', 'livedec'])
        cfg.number('input_valid_min', 0.0)
        cfg.number('input_valid_max', 300.0)

        return cfg.get_config()
