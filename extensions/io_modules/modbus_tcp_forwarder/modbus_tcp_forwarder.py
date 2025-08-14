"""
Forward live data as a Modbus TCP server
"""
import struct
import traceback
from typing import Optional, Dict, Union, List
from dataclasses import dataclass

import environ
from pyModbusTCP.server import ModbusServer

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.data_interface.module_meta_factory import ModuleMetaFactory
from vif.data_interface.network_messages import Status

from io_modules.modbus_tcp_forwarder.config import ModbusTCPForwarderConfig


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='ModbusTCPForwarder')


@dataclass
class Var:
    module: str
    channel: str
    value: Optional[Union[int, float]]
    register: int  # modbus register


class ModbusTCPForwarder(IOModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME
        self.data_broker.capabilities.capture_data = False
        self.data_broker.capabilities.live_data = False

        self._server: Optional[ModbusServer] = None
        self._tcp_port: int = -1
        self.variables_to_mod_channel: Dict[str, Var] = {}

    def stop(self):
        if self._server:
            self._server.stop()
        self.logger.info('module closed')

    def command_validate_config(self, config: Dict) -> Status:
        nb_inputs = len(config['input_module_sub_mode_channel'])

        for x in config['input_module_sub_mode_channel']:
            if (len(x.split('=')) != 2 or
                    len(x.split('#')) != 2 or
                    not (len(x.split('/')) == 2 or len(x.split('/')) == 3)):
                return Status(error=True, title='invalid config', message=f'{x}: not valid')

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
        return Status(error=False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            if self._tcp_port != config['TCP_port']:
                if self._server:
                    self._server.stop()
                self._server = ModbusServer(host='0.0.0.0', port=config['TCP_port'], no_block=True)
                self._server.start()
                self._tcp_port = config['TCP_port']

            modules = []
            sub_all = []
            dbids = []
            custom_dbids = False
            if len(config['input_module_dbid']) == len(config['input_module_sub_mode_channel']):
                custom_dbids = True  # only use configurable dbids if in config
            self.variables_to_mod_channel = {}
            out_registers = []
            for idx, r in enumerate(config['input_module_sub_mode_channel']):
                # 'PIDController/PIDController/liveall#output=1000'
                in_ch, out_register = r.split('=')
                out_register = int(out_register)
                if out_register in out_registers or (out_register + 1) in out_registers:
                    self.logger.error('duplicate output register: %d or %d', out_register, out_register + 1)
                    return Status(error=True, title='invalid config', message=f'{r}: duplicate output register')
                out_registers.extend([out_register, out_register + 1])
                m, channel = in_ch.split('#')
                split_config = m.split('/')
                if len(split_config) == 2:
                    module = split_config[0] + '/' + split_config[0]
                    mode = split_config[1]
                elif len(split_config) == 3:
                    module = split_config[0] + '/' + split_config[1]
                    mode = split_config[2]
                else:
                    return Status(error=True, title='invalid config', message=f'{r}: not valid')
                if module not in modules:
                    modules.append(module)
                    sub_all.append(True if mode == 'liveall' else False)
                    if custom_dbids and len(config['input_module_dbid'][idx]) > 0:
                        dbids.append(config['input_module_dbid'][idx])
                    else:
                        dbids.append(self.module_interface.db_id)  # our own databeam id
                self.variables_to_mod_channel[out_register] = Var(module=module, channel=channel, value=None,
                                                                  register=int(out_register))

            self.logger.info('subscribing to modules: %s (%s), sub_all: %s', modules, dbids, sub_all)
            self.logger.info('variables_to_mod_channel: %s', self.variables_to_mod_channel)

            self.module_interface.live_data_receiver.request_live_data(modules=modules, sub_all=sub_all,
                                                                       data_callback=self._data_received, db_ids=dbids)

            return Status(error=False)

        except Exception as e:
            self.logger.error(f'error applying config: {type(e).__name__}: {e}\n{traceback.format_exc()}')
            return Status(error=True, title=type(e).__name__, message=str(e))

    def command_get_meta_data(self) -> ModuleMetaFactory:
        meta_cfg = ModuleMetaFactory()
        return meta_cfg

    def command_get_schemas(self) -> List[Dict]:
        return [{
            'type': 'object',
            'properties': {}
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

            # update server register values
            for k, v in self.variables_to_mod_channel.items():
                if v.value is not None and self._server:
                    if isinstance(v.value, float):
                        # Pack float into two 16-bit integers (big endian)
                        float_bytes = struct.pack('>f', v.value)
                        reg_high, reg_low = struct.unpack('>HH', float_bytes)
                    elif isinstance(v.value, int):
                        int_bytes = v.value.to_bytes(4, byteorder='big')
                        reg_high, reg_low = struct.unpack('>HH', int_bytes)
                    else:
                        self.logger.error(f'EX data_received ({data}) - {type(v.value).__name__}: '
                                          f'{v.value} not supported')
                        continue
                    self._server.data_bank.set_input_registers(address=v.register, word_list=[reg_high, reg_low])

        except Exception as e:
            self.logger.error(f'EX data_received ({data}) - {type(e).__name__}: {e}')
            self.logger.debug('EX traceback: \n%s', traceback.format_exc())


if __name__ == '__main__':
    main(ModbusTCPForwarder, ModbusTCPForwarderConfig, environ.to_config(ModuleEnv).MODULE_NAME)
