import json
from typing import List, Union, Self, Optional
from enum import IntEnum
from abc import ABC, abstractmethod


class Reply(ABC):
    @abstractmethod
    def get_dict(self) -> dict:
        ...

    @classmethod
    @abstractmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        ...


class Status(Reply):
    def __init__(self, error: bool, title: str = "title", message: str = "message"):
        self.error = error
        self.title = title
        self.message = message

    def get_dict(self) -> dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, status_dict) -> Self:
        return cls(status_dict['error'], status_dict['title'], status_dict['message'])

    def serialize(self) -> str:
        return json.dumps(self.get_dict())

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(data['error'], data['title'], data['message'])


class MetaDataQueryCmd(IntEnum):
    SET = 1
    GET = 2


class MetaDataQuery:
    def __init__(self, cmd: MetaDataQueryCmd, system_meta_json: str = "", user_meta_json: str = ""):
        self.cmd = cmd
        self.system_meta_json = system_meta_json
        self.user_meta_json = user_meta_json

    def get_dict(self) -> dict:
        return {'cmd': self.cmd.value, 'system_meta_json': self.system_meta_json,
                'user_meta_json': self.user_meta_json}

    def serialize(self) -> str:
        return json.dumps(self.get_dict())

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(MetaDataQueryCmd(data['cmd']), data['system_meta_json'], data['user_meta_json'])


class MetaDataReply:
    def __init__(self, status: Status, system_meta_json: str = "{}", user_meta_json: str = "{}"):
        self.status: Status = status
        self.system_meta_json = system_meta_json
        self.user_meta_json = user_meta_json

    def get_dict(self) -> dict:
        return {'status': self.status.get_dict(), 'system_meta_json': self.system_meta_json,
                'user_meta_json': self.user_meta_json}

    def serialize(self) -> str:
        return json.dumps(self.get_dict())

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(Status.from_dict(data['status']), data['system_meta_json'], data['user_meta_json'])


class GetSchemasReply:
    def __init__(self, topic_names: dict):
        self.topic_names = topic_names

    def get_topic_names_list(self) -> List[str]:
        return self.topic_names["topic_names"]

    def serialize(self) -> str:
        return json.dumps(self.topic_names)

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        topic_data = json.loads(json_str)
        return cls(topic_data)


class Module:
    def __init__(self, name: str = "default_name", module_type: str = "default_type"):
        self.name = name
        self.type = module_type

    def get_dict(self) -> dict:
        return {'name': self.name, 'type': self.type}

    @classmethod
    def from_dict(cls, data):
        return cls(data['name'], data['type'])


class ModuleRegistryQueryCmd(IntEnum):
    UNSPECIFIED = 0
    REGISTER = 1
    REMOVE = 2
    LIST = 3


class ModuleRegistryQuery:
    def __init__(self, cmd: ModuleRegistryQueryCmd, module: Module = Module()):
        self.cmd: ModuleRegistryQueryCmd = cmd
        self.module = module

    def serialize(self) -> str:
        return json.dumps({'cmd': self.cmd.value,
                           'module': self.module.get_dict()})

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(ModuleRegistryQueryCmd(data['cmd']), Module.from_dict(data['module']))


class ModuleRegistryReply(Reply):
    def __init__(self, status: Status, modules: Optional[List[Module]] = None):
        self.status: Status = status
        self.modules: List[Module] = [] if modules is None else modules

    def get_dict(self) -> dict:
        return {'status': self.status.get_dict(), 'modules': [x.get_dict() for x in self.modules]}

    def serialize(self) -> str:
        return json.dumps(self.get_dict())

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(Status.from_dict(data['status']), [Module.from_dict(x) for x in data['modules']])


class SystemControlQueryCmd(IntEnum):
    UNSPECIFIED = 0
    DOCKER_RESTART = 1
    DOCKER_PULL = 2
    SHUTDOWN = 3
    REBOOT = 4
    SYNC_TIME = 5


class SystemControlQuery:
    def __init__(self, cmd: SystemControlQueryCmd, target_iso_time: str = ""):
        self.cmd: SystemControlQueryCmd = cmd
        self.target_iso_time: str = target_iso_time

    def serialize(self) -> str:
        return json.dumps({'cmd': self.cmd.value, 'target_iso_time': self.target_iso_time})

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(SystemControlQueryCmd(data['cmd']), data['target_iso_time'])


class SystemControlReply(Reply):
    def __init__(self, status: Status):
        self.status: Status = status

    def get_dict(self) -> dict:
        return {'status': self.status.get_dict()}

    def serialize(self) -> str:
        return json.dumps(self.get_dict())

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(Status.from_dict(data['status']))


class ModuleConfigQueryCmd(IntEnum):
    UNSPECIFIED = 0
    SET = 1
    GET = 2
    GET_DEFAULT = 3


class ModuleConfigQuery:
    def __init__(self, cmd: ModuleConfigQueryCmd, cfg_json: str = ""):
        self.cmd: ModuleConfigQueryCmd = cmd
        self.cfg_json: str = cfg_json

    def get_dict(self) -> dict:
        return {'cmd': self.cmd.value, 'cfg_json': self.cfg_json}

    def serialize(self) -> str:
        return json.dumps(self.get_dict())

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(ModuleConfigQueryCmd(data['cmd']), data['cfg_json'])


class ModuleConfigReply(Reply):
    def __init__(self, status: Status, cfg_json: str = "{}"):
        self.status: Status = status
        self.cfg_json: str = cfg_json

    def get_dict(self) -> dict:
        return {'status': self.status.get_dict(), 'json': self.cfg_json}

    def serialize(self) -> str:
        return json.dumps(self.get_dict())

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(Status.from_dict(data['status']), data['json'])


class ModuleDataConfigCmd(IntEnum):
    UNSPECIFIED = 0
    SET = 1
    GET = 2


class ModuleDataConfig:
    def __init__(self, enable_capturing: bool = False, enable_live_all_samples: bool = False,
                 enable_live_fixed_rate: bool = False, live_rate_hz: float = 1.0):
        self.enable_capturing: bool = enable_capturing
        self.enable_live_all_samples: bool = enable_live_all_samples
        self.enable_live_fixed_rate: bool = enable_live_fixed_rate
        self.live_rate_hz: float = live_rate_hz

    def get_dict(self) -> dict:
        return self.__dict__

    def serialize(self, indent=None) -> str:
        return json.dumps(self.__dict__, indent=indent)

    @classmethod
    def from_dict(cls, data) -> Self:
        return cls(data['enable_capturing'], data['enable_live_all_samples'],
                   data['enable_live_fixed_rate'], data['live_rate_hz'])

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        return cls.from_dict(json.loads(json_str))


class ModuleDataConfigQuery:
    def __init__(self, cmd: ModuleDataConfigCmd, module_data_config: ModuleDataConfig = ModuleDataConfig()):
        self.cmd: ModuleDataConfigCmd = cmd
        self.module_data_config: ModuleDataConfig = module_data_config

    def serialize(self) -> str:
        return json.dumps({'cmd': self.cmd.value, 'config': self.module_data_config.get_dict()})

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(ModuleDataConfigCmd(data['cmd']), ModuleDataConfig.from_dict(data['config']))


class ModuleDataConfigReply(Reply):
    def __init__(self, status: Status, config: ModuleDataConfig = ModuleDataConfig()):
        self.status: Status = status
        self.config: ModuleDataConfig = config

    def get_dict(self) -> dict:
        return {'status': self.status.get_dict(), 'config': self.config.get_dict()}

    def serialize(self) -> str:
        return json.dumps(self.get_dict())

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(Status.from_dict(data['status']), ModuleDataConfig.from_dict(data['config']))


class ModuleConfigEventCmd(IntEnum):
    UNSPECIFIED = 0
    BUTTON = 1


class ModuleConfigEvent:
    def __init__(self, cmd: ModuleConfigEventCmd, cfg_key: str):
        self.cmd: ModuleConfigEventCmd = cmd
        self.cfg_key = cfg_key

    def serialize(self) -> str:
        return json.dumps({'cmd': self.cmd.value, 'cfg_key': self.cfg_key})

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(ModuleConfigEventCmd(data['cmd']), data['cfg_key'])


class ModuleConfigEventReply(Reply):
    def __init__(self, status: Status):
        self.status: Status = status

    def get_dict(self) -> dict:
        return {'status': self.status.get_dict()}

    def serialize(self) -> str:
        return json.dumps({'status': self.status.get_dict()})

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(Status.from_dict(data['status']))


class DocumentationReply(Reply):
    def __init__(self, html_text: str):
        self.html_text: str = html_text

    def get_dict(self) -> dict:
        return {'html_text': self.html_text}

    def serialize(self) -> str:
        return json.dumps({'html_text': self.html_text})

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(data['html_text'])


class IOEvent:
    def __init__(self, json_data: str):
        self.json_data = json_data

    def serialize(self) -> str:
        return json.dumps({'json_data': self.json_data})

    @classmethod
    def deserialize(cls, json_str) -> Self:
        data = json.loads(json_str)
        return cls(data['json_data'])


class MeasurementInfo:
    def __init__(self, name: str = "", run_id: int = 0, run_tag: str = ""):
        self.name: str = name
        self.run_id: int = run_id
        self.run_tag: str = run_tag

    def get_dict(self) -> dict:
        return self.__dict__

    def serialize(self) -> str:
        return json.dumps(self.get_dict())

    @classmethod
    def from_dict(cls, data) -> Self:
        return cls(data['name'], data['run_id'], data['run_tag'])

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(data['name'], data['run_id'], data['run_tag'])


class StartStopCmd(IntEnum):
    UNSPECIFIED = 0
    START = 1
    STOP = 2
    RESTART = 3


class StartStop:
    def __init__(self, cmd: StartStopCmd):
        self.cmd = cmd

    def serialize(self) -> str:
        return json.dumps({'cmd': self.cmd.value})

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(StartStopCmd(data['cmd']))


class StartStopReply(Reply):
    def __init__(self, status: Status):
        self.status: Status = status

    def get_dict(self) -> dict:
        return {'status': self.status.get_dict()}

    def serialize(self) -> str:
        return json.dumps(self.get_dict())

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(Status.from_dict(data['status']))


class MeasurementStateType(IntEnum):
    UNSPECIFIED = 0
    CAPTURING = 1
    SAMPLING = 2
    IDLE = 3
    PREPARE_SAMPLING = 4
    PREPARE_CAPTURING = 5


class MeasurementState:
    def __init__(self, state: MeasurementStateType, measurement_info: MeasurementInfo = MeasurementInfo()):
        self.state: MeasurementStateType = state
        self.measurement_info: MeasurementInfo = measurement_info

    def get_dict(self) -> dict:
        return {'state': self.state.value, 'measurement_info': self.measurement_info.get_dict()}

    def serialize(self) -> str:
        return json.dumps(self.get_dict())

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(MeasurementStateType(data['state']), MeasurementInfo.from_dict(data['measurement_info']))


class ExternalDataBeamQuery:
    def __init__(self):
        pass

    @staticmethod
    def serialize() -> str:
        return json.dumps({})


class ExternalDataBeamQueryReply(Reply):
    def __init__(self, db_id_list: List[str], hostname_list: List[str]):
        self.db_id_list = db_id_list
        self.hostname_list = hostname_list

    def get_dict(self) -> dict:
        return {'db_id_list': self.db_id_list, 'hostname_list': self.hostname_list}

    def serialize(self) -> str:
        return json.dumps(self.get_dict())

    @classmethod
    def deserialize(cls, json_str: Union[str, bytes]) -> Self:
        data = json.loads(json_str)
        return cls(data['db_id_list'], data['hostname_list'])


if __name__ == '__main__':
    # meta data query test
    meta_data_query = MetaDataQuery(MetaDataQueryCmd.SET, "", "")
    m = MetaDataQuery.deserialize(meta_data_query.serialize())

    # meta data reply test
    meta_data_reply = MetaDataReply(Status(False, "T", "M"), "", "")
    meta_data_reply_str = meta_data_reply.serialize()
    meta_data_reply_deserialized = MetaDataReply.deserialize(meta_data_reply_str)

    # module registry query test
    module_registry_query = ModuleRegistryQuery(ModuleRegistryQueryCmd.REGISTER, Module("module_name", "module_type"))
    module_registry_query_str = module_registry_query.serialize()
    module_registry_query_deserialized = ModuleRegistryQuery.deserialize(module_registry_query_str)

    # module registry reply test
    module_registry_reply = ModuleRegistryReply(Status(False, "T", "M"), [Module("A", "Ab"), Module("B", "Bb")])
    module_registry_reply_str = module_registry_reply.serialize()
    module_registry_reply_deserialized = ModuleRegistryReply.deserialize(module_registry_reply_str)

    # system control query test
    system_control_query = SystemControlQuery(SystemControlQueryCmd.SYNC_TIME, "2007-03-04T21:08:12")
    system_control_query_str = system_control_query.serialize()
    system_control_query_deserialized = SystemControlQuery.deserialize(system_control_query_str)

    # system control reply test
    system_control_reply = SystemControlReply(Status(False, "T", "M"))
    system_control_reply_str = system_control_reply.serialize()
    system_control_reply_deserialized = SystemControlReply.deserialize(system_control_reply_str)

    # module config query test
    module_config_query = ModuleConfigQuery(ModuleConfigQueryCmd.SET, json.dumps({'string_field': "bla"}))
    module_config_query_str = module_config_query.serialize()
    module_config_query_deserialized = ModuleConfigQuery.deserialize(module_config_query_str)

    # module config reply test
    module_config_reply = ModuleConfigReply(Status(True, "T", "M"), json.dumps({'default_cfg_field': "bla"}))
    module_config_reply_str = module_config_reply.serialize()
    module_config_reply_deserialized = ModuleConfigReply.deserialize(module_config_reply_str)

    # module data config query test
    module_data_config_query = ModuleDataConfigQuery(ModuleDataConfigCmd.SET, ModuleDataConfig())
    module_data_config_query_str = module_data_config_query.serialize()
    module_data_config_query_deserialized = ModuleDataConfigQuery.deserialize(module_data_config_query_str)

    # module data config reply test
    module_data_config_reply = ModuleDataConfigReply(Status(True, "T", "M"), ModuleDataConfig())
    module_data_config_reply_str = module_data_config_reply.serialize()
    module_data_config_reply_deserialized = ModuleDataConfigReply.deserialize(module_data_config_reply_str)

    # documentation reply test
    documentation_reply = DocumentationReply("HTML TEXT")
    documentation_reply_str = documentation_reply.serialize()
    documentation_reply_deserialized = DocumentationReply.deserialize(documentation_reply_str)

    # io_event test
    io_event = IOEvent("Json data string")
    io_event_str = io_event.serialize()
    io_event_deserialized = io_event.deserialize(io_event_str)

    # measurement info test
    meas_info = MeasurementInfo("measurement name", 115, "run tag string")
    meas_info_str = meas_info.serialize()
    meas_info_deserialized = MeasurementInfo.deserialize(meas_info_str)

    # start stop test
    start_stop = StartStop(StartStopCmd.START)
    start_stop_str = start_stop.serialize()
    start_stop_deserialized = StartStop.deserialize(start_stop_str)

    # start stop reply test
    start_stop_reply = StartStopReply(Status(False, "T", "M"))
    start_stop_reply_str = start_stop_reply.serialize()
    start_stop_reply_deserialized = StartStopReply.deserialize(start_stop_reply_str)

    # measurement state test
    measurement_state = MeasurementState(MeasurementStateType.SAMPLING, MeasurementInfo("measurement name", 115, "Tag"))
    measurement_state_str = measurement_state.serialize()
    measurement_state_deserialized = MeasurementState.deserialize(measurement_state_str)

    # module config event
    module_config_event = ModuleConfigEvent(ModuleConfigEventCmd.BUTTON, 'my button')
    module_config_event_str = module_config_event.serialize()
    module_config_event_deserialized = ModuleConfigEvent.deserialize(module_config_event_str)

    print("done")
