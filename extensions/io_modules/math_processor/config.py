from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory

class MathProcessorConfig(BaseConfig):

    Name = 'math_processor'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.string_array('input_module_sub_mode_channel', ['PIDController/PIDController/liveall#output']).label(
            'Inputs: module/topic/sub_mode#channel').resizeable()
        cfg.string_array('input_module_dbid', ['']).label('Input DBIDs (opt)').resizeable()
        cfg.string_array('input_names_internal', ['v1']).label('Internal Input Names').resizeable()
        cfg.string('calculation', 'v1 * v1')
        cfg.string('result_channel_name', 'result')

        return cfg.get_config()