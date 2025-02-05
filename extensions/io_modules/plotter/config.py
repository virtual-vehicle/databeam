from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory
import json

class PlotterConfig(BaseConfig):

    Name = 'plotter'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.integer_array("layout", [3, 2]).resizeable()
        cfg.string_array('modules', ["Ping"]).resizeable().hidden()
        cfg.string_array('plot_types', ["Line"]).resizeable().hidden()
        cfg.string_array('options', ['{}']).resizeable().hidden()
        cfg.string_array('channels', ['']).resizeable().hidden()
        cfg.string('live_data_source', '{}').hidden()

        return cfg.get_config()
