"""
Math processor for live data
"""
import traceback
from typing import Dict, Union, List, Optional
import time
import ast
import operator as op
from dataclasses import dataclass
import math
import builtins
from functools import cache

import environ

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.data_interface.network_messages import Status

from io_modules.math_processor.config import MathProcessorConfig

# https://stackoverflow.com/a/9558001
# and similar to https://github.com/danthedeckie/simpleeval/blob/master/simpleeval.py
# with help from https://stackoverflow.com/a/69644059
# and https://stackoverflow.com/a/68732605

MATH_FUNCTIONS = {f: getattr(math, f) for f in dir(math) if "__" not in f}
BUILTIN_FUNCTIONS = {f: getattr(builtins, f) for f in ['min', 'max', 'abs', 'pow', 'bool', 'int']}


def check_math(x: str, *args):
    @cache
    def get_fun(x_: str):
        if x_ in BUILTIN_FUNCTIONS:
            func = BUILTIN_FUNCTIONS[x_]
        elif x_ in MATH_FUNCTIONS:
            func = MATH_FUNCTIONS[x_]
        else:
            msg = f"Unknown math function: {x_}()"
            raise SyntaxError(msg)
        return func

    fun = get_fun(x)
    return fun(*args)


# supported operators
operators = {ast.Add: op.add,
             ast.Sub: op.sub,
             ast.Mult: op.mul,
             ast.Div: op.truediv,
             ast.Mod: op.mod,
             ast.Pow: op.pow,
             ast.Call: check_math,
             ast.BitXor: op.xor,
             ast.BitOr: op.or_,
             ast.BitAnd: op.and_,
             ast.USub: op.neg,  # unary minus
             ast.UAdd: op.pos,  # unary plus
             ast.UnaryOp: ast.UnaryOp,
             }


def eval_expr(expr, values_dict):
    """
    >>> eval_expr(ast.parse('var + 2*3**(4^5) / max(6, -7)', mode='eval').body, {'var': 41.0})
    42.0
    """
    return eval_(expr, values_dict)


def eval_(node: Union[ast.Constant, ast.UnaryOp, ast.BinOp, ast.Name, ast.Call], values_dict):
    match node:
        case ast.Constant(value) if isinstance(value, int):
            return value
        case ast.Constant(value) if isinstance(value, float):
            return value
        case value if isinstance(value, ast.Name):  # handle variables
            return values_dict[node.id]
        case ast.BinOp(left, op, right):
            return operators[type(op)](eval_(left, values_dict), eval_(right, values_dict))
        case ast.UnaryOp(op, operand):  # e.g., -1
            return operators[type(op)](eval_(operand, values_dict))
        case value if isinstance(value, ast.Call):
            args = [eval_(x, values_dict) for x in node.args]
            return check_math(node.func.id, *args)
        case _:
            raise TypeError(node)


@dataclass
class Var:
    module: str
    channel: str
    value: Optional[Union[int, float]]


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='MathProcessor')


class MathProcessor(IOModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME

        self.variables_to_mod_channel: Dict[str, Var] = {}
        self.syntax_error_shown = False

        self.math_expr: Optional[ast.expr] = None

    def command_validate_config(self, config) -> Status:
        # compare lengths of all lists
        nb_inputs = len(config['input_module_sub_mode_channel'])
        for li in ['input_names_internal']:
            if len(config[li]) != nb_inputs:
                return Status(error=True, title='invalid config', message=f'{li}: length not valid')

        for x in config['input_module_sub_mode_channel']:
            if len(x.split('#')) != 2 or not (len(x.split('/')) == 2 or len(x.split('/')) == 3):
                return Status(error=True, title='invalid config', message=f'{x}: not valid')

        for i in config['input_names_internal']:
            if len(i) < 1:
                return Status(error=True, title='invalid config', message=f'input_names_internal not valid')

        if len(config['result_channel_name']) < 1:
            return Status(error=True, title='invalid config', message='result_channel_name not valid')

        use_custom_ids = False
        for x in config['input_module_dbid']:
            # if any dbid is given, size of array must match modules
            if len(x) > 0:
                use_custom_ids = True
                if len(config['input_module_dbid']) != nb_inputs:
                    return Status(error=True, title='invalid config', message='input_module_dbid: length not valid')
                break
        if use_custom_ids:
            for x in config['input_module_dbid']:
                if len(x) == 0:
                    return Status(error=True, title='invalid config', message='input_module_dbid not valid')

        # TODO walk through config['input_module_sub_mode_channel'] and check if same modules also share same sub_mode

        return Status(error=False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        # reset flag that error was shown in GUI
        self.syntax_error_shown = False
        try:
            modules = []
            sub_all = []
            dbids = []
            custom_dbids = False
            if len(config['input_module_dbid']) == len(config['input_module_sub_mode_channel']):
                custom_dbids = True  # only use configurable dbids if in config
            self.variables_to_mod_channel = {}
            for idx, r in enumerate(config['input_module_sub_mode_channel']):
                # 'PIDController/liveall#output'
                m, channel = r.split('#')
                split_config = m.split('/')
                if len(split_config) == 2:
                    module = split_config[0] + '/' + split_config[0]
                    mode = split_config[1]
                elif len(split_config) == 3:
                    module = split_config[0] + '/' + split_config[1]
                    mode = split_config[1]
                else:
                    return Status(error=False)
                if module not in modules:
                    modules.append(module)
                    sub_all.append(True if mode == 'liveall' else False)
                    if custom_dbids and len(config['input_module_dbid'][idx]) > 0:
                        dbids.append(config['input_module_dbid'][idx])
                    else:
                        dbids.append(self.module_interface.db_id)  # our own databeam id
                self.variables_to_mod_channel[config['input_names_internal'][idx]] = Var(module=module, channel=channel,
                                                                                         value=None)

            self.logger.info('subscribing to modules: %s (%s), sub_all: %s', modules, dbids, sub_all)
            self.logger.info('variables_to_mod_channel: %s', self.variables_to_mod_channel)

            self.module_interface.live_data_receiver.request_live_data(modules=modules, sub_all=sub_all,
                                                                       data_callback=self._data_received, db_ids=dbids)

            self.math_expr = ast.parse(self.config_handler.config['calculation'], mode='eval').body
            return Status(error=False)

        except Exception as e:
            self.logger.error(f'error applying config: {type(e).__name__}: {e}\n{traceback.format_exc()}')
            return Status(error=True, title=type(e).__name__, message=str(e))

    def command_get_schemas(self) -> List[Dict]:
        return [{
            'type': 'object',
            'properties': {
                self.config_handler.config['result_channel_name']: {'type': 'number'}
            }
        }]

    def _data_received(self, db_id: str, module: str, data: Dict) -> None:
        try:
            new_values = {}
            for name, var in self.variables_to_mod_channel.items():
                if var.module == module:
                    new_values[name] = data[var.channel]

            # apply value updates
            for k, v in new_values.items():
                self.variables_to_mod_channel[k].value = v

            # evaluate calculation expression
            values = {k: v.value for k, v in self.variables_to_mod_channel.items()}
            # check if any value is None
            if not any(v is None for v in values.values()):
                result = eval_expr(self.math_expr, values)
                self.data_broker.data_in(time.time_ns(), {self.config_handler.config['result_channel_name']: result})
        except SyntaxError as e:
            if not self.syntax_error_shown:
                self.syntax_error_shown = True
                self.logger.error(f'EX data_received - {type(e).__name__}: {e}')
                self.module_interface.log_gui(f'{type(e).__name__}: {e}')
        except Exception as e:
            self.logger.error(f'EX data_received ({data}) - {type(e).__name__}: {e}')
            self.logger.debug('EX traceback: \n%s', traceback.format_exc())


if __name__ == '__main__':
    main(MathProcessor, MathProcessorConfig, environ.to_config(ModuleEnv).MODULE_NAME)
