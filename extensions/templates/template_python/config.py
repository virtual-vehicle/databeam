from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory


class TemplateConfig(BaseConfig):  # TODO adopt config name

    # TODO replace with proper name/type of config (use lower_case)
    Name = 'template'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()

        cfg.string('text_value', 'xyz')
        cfg.integer('x_value', 1234).label('Custom labels!')
        cfg.number('float_value', 1.23)
        cfg.boolean('show_more', False).label('Tick me to show more!')
        # make an entry visible only if another entry has certain value
        cfg.integer('conditional', 42).visible('show_more', True).indent()

        # select from a list of options
        cfg.string("string_select_field", "Option 1").select(["Option 1", "Option 2", "Option 3"])

        # all types are also available as arrays
        cfg.string_array('servers', ['v2c2.at']).resizeable().label('My Servers')
        # fixed size array
        cfg.integer_array('fixed_sized_array', [1, 2, 3])
        # variable size array
        cfg.number_array('numbers', [1.1, 2.2]).resizeable()
        cfg.boolean_array('checkboxes', [True, False]).resizeable()

        # buttons will call "command_config_event(cfg_key)" callback in module
        cfg.string('my_button', "Event Button").label("Hit That Button!").button()

        # create hidden entry: not shown in GUI, but we can save stuff
        cfg.string('hidden_entry', 'hidden values').hidden()

        # nested configs
        cfg2 = ConfigFactory()
        cfg2.string('nested_var', 'abc')

        # nested configs can be nested as well
        cfg3 = ConfigFactory()
        cfg3.string('this_is_going_deep', '<-.->')
        cfg2.object('nested_obj', cfg3)

        # add nested config to main config
        cfg.object('myobj', cfg2)

        return cfg.get_config()
