from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory


class ModbusTCPForwarderConfig(BaseConfig):

    Name = 'modbus_tcp_forwarder'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()

        cfg.integer('TCP_port', 502)

        cfg.string_array('input_module_sub_mode_channel',
                         ['PIDController/PIDController/liveall#output=1000']).resizeable().label(
            'Inputs: module/topic/sub_mode#channel=REGISTER')
        cfg.string_array('input_module_dbid', []).resizeable().label('Input DBIDs (opt)')

        return cfg.get_config()
