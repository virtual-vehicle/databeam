"""
Allows the Rest API to communicate with the controller.
Can fetch/set documentation, config, meta data and measurement data of modules.
Also is able to start/stop sampling/capturing, and send system commands.
"""

import threading
import json
from typing import Optional

from vif.data_interface.helpers import wait_for_controller

from vif.logger.logger import LoggerMixin
from vif.data_interface.connection_manager import ConnectionManager, Key
from vif.websockets.websocket_api import WebSocketAPI
from vif.data_interface.network_messages import (MeasurementState, ModuleRegistryQuery, ModuleDataConfig,
                                                 ModuleRegistryReply, Module,
                                                 Status, StartStop, StartStopReply,
                                                 MeasurementStateType, StartStopCmd, ModuleRegistryQueryCmd,
                                                 IOEvent, ModuleConfigQuery,
                                                 ModuleConfigQueryCmd, ModuleConfigReply, ModuleDataConfigQuery,
                                                 ModuleDataConfigCmd, ModuleDataConfigReply, DocumentationReply,
                                                 MeasurementInfo, MetaDataQueryCmd, MetaDataQuery,
                                                 MetaDataReply, SystemControlQuery, SystemControlReply,
                                                 SystemControlQueryCmd, ModuleConfigEvent, ModuleConfigEventReply,
                                                 ModuleConfigEventCmd)


class ControllerAPI(LoggerMixin):
    def __init__(self, *args, databeam_id, websocket_api: WebSocketAPI, shutdown_ev: threading.Event,
                 db_router: str, **kwargs):
        super().__init__(*args, **kwargs)

        self._databeam_id = databeam_id
        assert len(self._databeam_id) > 0, 'DB_ID environment variable not set'
        self._websocket_api = websocket_api
        self.logger.info('Init with databeam id: ' + self._databeam_id)
        self.shutdown_ev = shutdown_ev

        self.cm = ConnectionManager(router_hostname=db_router, db_id=self._databeam_id, node_name='r',
                                    shutdown_event=shutdown_ev, max_parallel_req=5)

    def start(self):
        # wait for connection to controller
        wait_for_controller(logger=self.logger, shutdown_ev=self.shutdown_ev, cm=self.cm, db_id=self._databeam_id)

        for key, cb in [(Key(self._databeam_id, 'c', 'job_list'), self._cb_jobs),
                        ]:
            self.cm.subscribe(key, cb)

    def shutdown(self):
        self.logger.info("Shutdown initiated")
        self.cm.close()
        self.cm = None
        self.logger.info("Shutdown complete")

    def _cb_jobs(self, key, data: bytes):
        json_str = data.decode('utf-8')
        self._websocket_api.broadcast_json_str("job", json_str)

    def _handle_reply_exception(self, ex: Exception, reply: Optional[bytes], func_name: str, target: str):
        if reply is None or type(ex).__name__ == 'StopIteration':
            title = target + ": Timeout Error"
            message = f'{func_name} - no reply from "{target}"'
        else:
            title = target + ": Unknown error"
            message = f'{func_name} failed ({type(ex).__name__}): {ex}'

        # log error
        self.logger.error(message)

        # return status with error
        return {'status': Status(True, title, message).get_dict()}

    def get_module_latest(self, module):
        try:
            reply = self.cm.request(Key(self._databeam_id, f'm/{module}', 'get_latest'))
            if reply is not None:
                json_str = reply.decode('utf-8')
                return json_str
        except Exception as e:
            self.logger.error(f'get_module_latest failed ({type(e).__name__}): {e}')
        return json.dumps({})

    def get_documentation(self, module) -> dict:
        reply = None
        try:
            reply = self.cm.request(Key(self._databeam_id, f'm/{module}', 'get_docu'))
            html_str = DocumentationReply.deserialize(reply).html_text
            return {'documentation': html_str, 'status': Status(False).get_dict()}
        except Exception as e:
            return self._handle_reply_exception(e, reply, "get_documentation", module)

    def get_data_config_dict(self, module):
        message = ModuleDataConfigQuery(cmd=ModuleDataConfigCmd.GET)
        reply = None
        try:
            reply = self.cm.request(Key(self._databeam_id, f'm/{module}', 'data_config'), message.serialize())
            value = ModuleDataConfigReply.deserialize(reply)
            return value.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "get_data_config_dict", module)

    def set_data_config_dict(self, module, data_config):
        message = ModuleDataConfigQuery(cmd=ModuleDataConfigCmd.SET,
                                        module_data_config=ModuleDataConfig(**data_config))
        reply = None
        try:
            reply = self.cm.request(Key(self._databeam_id, f'm/{module}', 'data_config'), message.serialize())
            value: ModuleDataConfigReply = ModuleDataConfigReply.deserialize(reply)
            return value.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "set_data_config_dict", module)

    def get_metadata_dict(self):
        reply = None
        try:
            message = MetaDataQuery(cmd=MetaDataQueryCmd.GET)
            reply = self.cm.request(Key(self._databeam_id, 'c', 'metadata'), message.serialize())
            value = MetaDataReply.deserialize(reply)
            return value.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "get_metadata_dict", 'Controller')

    def set_user_meta_string(self, user_meta_dict):
        reply = None
        try:
            message = MetaDataQuery(cmd=MetaDataQueryCmd.SET, user_meta_json=user_meta_dict)
            reply = self.cm.request(Key(self._databeam_id, 'c', 'metadata'), message.serialize())
            value = MetaDataReply.deserialize(reply)
            return value.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "set_user_meta_string", 'Controller')

    def set_system_meta_string(self, system_meta_dict):
        reply = None
        try:
            message = MetaDataQuery(cmd=MetaDataQueryCmd.SET, system_meta_json=system_meta_dict)
            reply = self.cm.request(Key(self._databeam_id, 'c', 'metadata'), message.serialize())
            value = MetaDataReply.deserialize(reply)
            return value.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "set_system_meta_string", 'Controller')

    def set_module_config_dict(self, module_name, cfg):
        reply = None
        try:
            message = ModuleConfigQuery(cmd=ModuleConfigQueryCmd.SET, cfg_json=json.dumps(cfg))
            reply = self.cm.request(Key(self._databeam_id, f'm/{module_name}', 'config'), message.serialize())
            value = ModuleConfigReply.deserialize(reply)
            return value.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "set_module_config_dict", module_name)

    def set_module_config_event(self, module_name, event_data):
        reply = None
        try:
            message = ModuleConfigEvent(ModuleConfigEventCmd.BUTTON, event_data['cfg_key'])
            reply = self.cm.request(Key(self._databeam_id, f'm/{module_name}', 'config_event'), message.serialize())
            value = ModuleConfigEventReply.deserialize(reply)
            return value.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "set_module_config_event", module_name)

    def get_module_config_dict(self, module_name):
        reply = None
        try:
            message = ModuleConfigQuery(cmd=ModuleConfigQueryCmd.GET)
            reply = self.cm.request(Key(self._databeam_id, f'm/{module_name}', 'config'), message.serialize())
            value = ModuleConfigReply.deserialize(reply)
            return value.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "get_module_config_dict", module_name)

    def get_module_default_config_dict(self, module_name):
        reply = None
        try:
            message = ModuleConfigQuery(cmd=ModuleConfigQueryCmd.GET_DEFAULT)
            reply = self.cm.request(Key(self._databeam_id, f'm/{module_name}', 'config'), message.serialize())
            value = ModuleConfigReply.deserialize(reply)
            return value.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "get_module_default_config_dict", module_name)

    def get_modules_dict(self) -> dict:
        self.logger.debug('get_modules_dict')
        reply = None
        try:
            message = ModuleRegistryQuery(cmd=ModuleRegistryQueryCmd.LIST)
            reply = self.cm.request(Key(self._databeam_id, 'c', 'module_registry'), message.serialize(), 2)
            value = ModuleRegistryReply.deserialize(reply)
            return value.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "get_modules_dict", "Controller")

    def get_modules_and_data_config_dict(self):
        modules = self.get_modules_dict()

        if modules['status']['error']:
            return modules

        for m in modules['modules']:
            data_config = self.get_data_config_dict(m['name'])

            if data_config['status']['error']:
                return data_config

            if 'config' in data_config:
                m.update(data_config['config'])

        return modules

    def send_command_start_capture(self) -> dict:
        reply = None
        try:
            message = StartStop(cmd=StartStopCmd.START)
            reply = self.cm.request(Key(self._databeam_id, 'c', 'cmd_capture'), message.serialize(), 3)
            message = StartStopReply.deserialize(reply)
            return message.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "send_command_start_capture", "Controller")

    def send_command_stop_capture(self) -> dict:
        reply = None
        try:
            message = StartStop(cmd=StartStopCmd.STOP)
            reply = self.cm.request(Key(self._databeam_id, 'c', 'cmd_capture'), message.serialize(), 6)
            message = StartStopReply.deserialize(reply)
            return message.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "send_command_stop_capture", "Controller")

    def send_command_start_sampling(self) -> dict:
        reply = None
        try:
            message = StartStop(cmd=StartStopCmd.START)
            reply = self.cm.request(Key(self._databeam_id, 'c', 'cmd_sampling'), message.serialize(), 3)
            message = StartStopReply.deserialize(reply)
            return message.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "send_command_start_sampling", "Controller")

    def send_command_stop_sampling(self) -> dict:
        self.logger.debug('send_command_stop_sampling')
        reply = None
        try:
            message = StartStop(cmd=StartStopCmd.STOP)
            reply = self.cm.request(Key(self._databeam_id, 'c', 'cmd_sampling'), message.serialize(), 6)
            message = StartStopReply.deserialize(reply)
            return message.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "send_command_stop_sampling", "Controller")

    def send_system_command(self, command_str: str):
        cmd_dict = {'docker_restart': SystemControlQueryCmd.DOCKER_RESTART,
                    'docker_pull': SystemControlQueryCmd.DOCKER_PULL,
                    'time_sync': SystemControlQueryCmd.SYNC_TIME,
                    'reboot': SystemControlQueryCmd.REBOOT,
                    'shutdown': SystemControlQueryCmd.SHUTDOWN}

        if command_str not in cmd_dict.keys():
            return {'status': Status(True, "System Command", "Command string not valid.").get_dict()}

        reply = None
        try:
            message = SystemControlQuery(cmd=cmd_dict[command_str])
            reply = self.cm.request(Key(self._databeam_id, 'c', 'system_control'), message.serialize(), 2)
            message = SystemControlReply.deserialize(reply)
            return message.get_dict()
        except Exception as e:
            return self._handle_reply_exception(e, reply, "send_system_command", "Controller")
