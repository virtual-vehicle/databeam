import json
import os
import re
import time
from datetime import datetime, timezone
import threading
from pathlib import Path
from typing import Type, Dict, Optional
import logging
import traceback
import signal
import multiprocessing

import environ
import orjson

from vif.logger.logger import LoggerMixin, log_reentrant
from vif.data_interface.data_broker import DataBroker
from vif.data_interface.live_data_receiver import LiveDataReceiver
from vif.data_interface.config_handler import ConfigHandler
from vif.data_interface.base_config import BaseConfig
from vif.data_interface.helpers import wait_for_controller

from vif.file_helpers.creation import create_directory
from vif.jobs.job_entry import LogJob, ReadyJob
from vif.data_interface.io_module import IOModule
from vif.data_interface.connection_manager import ConnectionManager, ConnectionException, Key
from vif.data_interface.network_messages import (MeasurementState, ModuleRegistryQuery, ModuleDataConfig,
                                                 ModuleRegistryReply, Module,
                                                 Status, StartStop, StartStopReply,
                                                 MeasurementStateType, StartStopCmd, ModuleRegistryQueryCmd,
                                                 IOEvent, ModuleConfigQuery,
                                                 ModuleConfigQueryCmd, ModuleConfigReply, ModuleDataConfigQuery,
                                                 ModuleDataConfigCmd, ModuleDataConfigReply, DocumentationReply,
                                                 MeasurementInfo, ModuleConfigEvent, ModuleConfigEventReply,
                                                 ExternalDataBeamQuery, ExternalDataBeamQueryReply,
                                                 GetSchemasReply)


@environ.config(prefix='')
class ModuleInterfaceEnv:
    LOGLEVEL = environ.var(help='logging level', default='INFO')
    CONFIG_DIR = environ.var(help='config directory without deploy version', converter=lambda x: Path(x).expanduser())
    DATA_DIR = environ.var(help='data directory without deploy version', converter=lambda x: Path(x).expanduser())
    DEPLOY_VERSION = environ.var(help='docker images tag', default='latest')
    DB_ID = environ.var(help='DataBeam domain name for communication', default='db')
    DB_ROUTER = environ.var(help='DataBeam router hostname to find other nodes', default='localhost')


class ModuleInterface(LoggerMixin):
    def __init__(self, *args, io_module_type: Type[IOModule], config_type: Type[BaseConfig],
                 shutdown_event: threading.Event, module_name: str, **kwargs):
        super().__init__(*args, **kwargs)

        self.__logger = logging.getLogger('IOModule')

        # parse environment variables to config
        try:
            self.env_cfg = environ.to_config(ModuleInterfaceEnv)
        except environ.MissingEnvValueError as e_main:
            raise KeyError(f'Missing environment variable: {e_main}')

        self.shutdown_ev = shutdown_event
        self.exit_return_value: int = 0

        self.__deploy_version = self.env_cfg.DEPLOY_VERSION
        self.__logger.info(f'DEPLOY_VERSION: {self.__deploy_version}')
        self.db_id = self.env_cfg.DB_ID
        assert len(self.db_id) > 0, 'DB_ID environment variable not set'
        self.__logger.info(f'DB_ID: {self.db_id}')

        # assign and create directory structure
        self.config_dir = Path('.')
        self.data_config_path = Path('.')

        # will be followed by / "measurement_name"
        self.data_dir = self.env_cfg.DATA_DIR / self.env_cfg.DEPLOY_VERSION

        self.cm = ConnectionManager(router_hostname=self.env_cfg.DB_ROUTER,
                                    db_id=self.db_id, node_name=f'm/{module_name}')

        self.__registered = False
        self.__controller_watchdog_thread: Optional[threading.Thread] = None

        self.state: MeasurementState = MeasurementState(state=MeasurementStateType.IDLE)
        self.data_config: ModuleDataConfig = ModuleDataConfig(enable_capturing=True, enable_live_all_samples=False,
                                                              enable_live_fixed_rate=False, live_rate_hz=1)
        self._sampling_active = False  # remember if sampling was explicitly enabled
        self.config_handler = ConfigHandler(config_type=config_type)
        self.live_data_receiver = LiveDataReceiver(con_mgr=self.cm, databeam_id=self.db_id)

        # create ready job
        self._ready_job: ReadyJob = ReadyJob(self.cm, self.db_id)
        self._ready_job.set_module_name(module_name)

        # set module name
        self.name = module_name

        # create data broker
        self.data_broker = DataBroker(db_id=self.db_id, db_router=self.env_cfg.DB_ROUTER, data_dir=self.data_dir,
                                      module_name=self.name, module_type=self.config_handler.type)

        # create io module instance
        self.module = io_module_type(module_interface=self)

    def log_gui(self, message: str) -> None:
        self.__logger.debug("log_gui: %s", message)
        time_ns = datetime.now(timezone.utc)
        time_str = time_ns.strftime("%H:%M:%S.%f")
        log_job = LogJob(self.cm, self.db_id)
        log_job.set_name(self.name).set_message(message).set_time(time_str).set_done().update()

    def set_ready_state(self, ready_state: bool):
        # leave if ready state did not change
        if ready_state == self._ready_job.get_ready():
            return

        # set new ready state and update job
        self._ready_job.set_ready(ready_state).update()

    def capturing_active(self):
        return self.state.state == MeasurementStateType.CAPTURING

    def sampling_active(self):
        return self.state.state == MeasurementStateType.SAMPLING

    def sampling_or_capturing_active(self):
        return self.capturing_active() or self.sampling_active()

    def prepare(self):
        # check if name is valid
        try:
            assert bool(re.fullmatch(r'[a-zA-Z0-9_]+', self.name))
        except AssertionError as e:
            self.__logger.error(f'Invalid name (only aA09_): "{self.name}"')
            raise e
        self.__logger.info(f'Preparing module "{self.name}" (type: {self.config_handler.type})')

        self.config_dir = (self.env_cfg.CONFIG_DIR / self.env_cfg.DEPLOY_VERSION /
                           f'{self.config_handler.type}-{self.name}')
        # create config and data directories
        create_directory(Path(self.config_dir))
        # set final config directory with assigned module name
        self.config_handler.set_config_dir(self.config_dir)

        self.data_broker.start_capture_process()

        # load data_config.json
        self.data_config_path = self.config_dir / 'data_config.json'
        try:
            with self.data_config_path.open('r') as f:
                self.data_config = ModuleDataConfig.deserialize(f.read())
                self.__logger.info(f'Data config loaded from {self.data_config_path}: {self.data_config.get_dict()}')
        except FileNotFoundError:
            # write default config
            self.__write_data_config()
        except Exception as e:
            self.__logger.error(f'EX data-cfg {type(e).__name__}: {e}\n{traceback.format_exc()}')
        self.data_broker.configure_live(self.data_config)

        # wait for connection to controller
        wait_for_controller(logger=self.__logger, shutdown_ev=self.shutdown_ev, cm=self.cm, db_id=self.db_id)

        if self.shutdown_ev.is_set():
            return

        # update ConnectionManager with known external dbids/hostnames from controller
        db_reg_resp = self.cm.request(Key(self.db_id, 'c', 'databeam_registry'),
                                      data=ExternalDataBeamQuery().serialize())
        dbid_hostnames = ExternalDataBeamQueryReply.deserialize(db_reg_resp)
        self.cm.set_external_databeams(dbid_hostnames.db_id_list, dbid_hostnames.hostname_list)

        # register queryables
        for q_key, q_cb in [(Key(self.db_id, f'm/{self.name}', 'ping'), self.__cb_ping),
                            (Key(self.db_id, f'm/{self.name}', 'config'), self.__cb_config),
                            (Key(self.db_id, f'm/{self.name}', 'config_event'), self.__cb_config_event),
                            (Key(self.db_id, f'm/{self.name}', 'data_config'), self.__cb_data_config),
                            (Key(self.db_id, f'm/{self.name}', 'prepare_sampling'), self.__cb_prepare_sampling),
                            (Key(self.db_id, f'm/{self.name}', 'stop_sampling'), self.__cb_stop_sampling),
                            (Key(self.db_id, f'm/{self.name}', 'get_docu'), self.__cb_get_docu),
                            (Key(self.db_id, f'm/{self.name}', 'prepare_capture'), self.__cb_prepare_capture),
                            (Key(self.db_id, f'm/{self.name}', 'stop_capture'), self.__cb_stop_capture),
                            (Key(self.db_id, f'm/{self.name}', 'get_latest'), self.__cb_get_latest),
                            (Key(self.db_id, f'm/{self.name}', 'get_metadata'), self.__cb_get_metadata),
                            (Key(self.db_id, f'm/{self.name}', 'get_schemas'), self.__cb_get_schemas)
                            ]:
            self.cm.declare_queryable(q_key, q_cb)

        # register publishers
        self.cm.declare_publisher(Key(self.db_id, f'm/{self.name}', 'event_out'))

        # Start after queryables are declared because it needs get_schemas
        self.data_broker.start_live_process()

        # register subscribers
        for sub_key, sub_cb in [(Key(self.db_id, f'm/{self.name}', 'event_in'), self.__cb_sub_event),
                                (Key(self.db_id, 'c', 'bc/start_sampling'), self.__cb_sub_start_sampling),
                                (Key(self.db_id, 'c', 'bc/start_capture'), self.__cb_sub_start_capture),
                                ]:
            self.cm.subscribe(sub_key, sub_cb)

    def register(self):
        message = ModuleRegistryQuery(cmd=ModuleRegistryQueryCmd.REGISTER,
                                      module=Module(name=self.name, module_type=self.config_handler.type))
        try:
            reply = self.cm.request(Key(self.db_id, 'c', 'module_registry'), message.serialize(), timeout=2)
            if reply is None:
                raise ConnectionException('registering failed: received None')
            value = ModuleRegistryReply.deserialize(reply)

            if not value.status.error:
                self.__logger.info('Successfully registered module with controller')
        except Exception as e:
            raise e

        # start controller watchdog
        if self.__controller_watchdog_thread is None:
            self.__controller_watchdog_thread = threading.Thread(target=self.controller_watchdog,
                                                                 name='controller_watchdog')
            self.__controller_watchdog_thread.start()

    def controller_watchdog(self):
        self.__logger.info('controller watchdog started')

        while not self.shutdown_ev.is_set():
            try:
                # repeated registration is used as heartbeat
                self.register()
            except ConnectionException as e:
                self.logger.warning(f'watchdog {type(e).__name__}: {e}')
            except Exception as e:
                self.__logger.error(f'watchdog register {type(e).__name__}: {e}\n{traceback.format_exc()}')

            self.shutdown_ev.wait(timeout=1)

        self.__logger.info('controller watchdog stopped')

    def teardown(self):
        self.__logger.info(f'tearing down module "{self.name}"')
        try:
            self._ready_job.set_ready(True).set_done().update()

            self.live_data_receiver.shutdown()

            # stop controller watchdog
            if self.__controller_watchdog_thread is not None:
                self.__controller_watchdog_thread.join()

            # unregister module from controller
            self.__logger.debug('removing module from controller')
            message = ModuleRegistryQuery(cmd=ModuleRegistryQueryCmd.REMOVE,
                                          module=Module(name=self.name, module_type=self.config_handler.type))
            try:
                reply = self.cm.request(Key(self.db_id, 'c', 'module_registry'), message.serialize(), timeout=1)
                if reply is None:
                    raise ConnectionException('unregister failed: received None')
                value = ModuleRegistryReply.deserialize(reply)
                del reply
            except ConnectionException as e:
                self.__logger.error(f'teardown failed ({type(e).__name__}): {e}')
            except Exception as e:
                self.__logger.error(f'teardown failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            else:
                if value.status.error:
                    self.__logger.error('removing failed / controller response: '
                                        f'{value.status.title}: {value.status.message}')
                self.__logger.info('successfully removed module from controller')

            # stop capturing and sampling
            self.module.command_stop_capturing()
            self.data_broker.stop_capturing()
            self.data_broker.close()
            self.module.command_stop_sampling()

            self.cm.close()

            # stop module
            self.module.stop()

        except Exception as e:
            self.__logger.error(f'teardown failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')

        self.__logger.info('teardown complete')

    def send_event(self, event_data: Dict) -> None:
        try:
            io_event = IOEvent(json_data=json.dumps(event_data))
        except Exception as e:
            self.__logger.error(f'event json encoding failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return
        self.__logger.debug(f'send event: {io_event.json_data}')
        self.cm.publish(Key(self.db_id, f'm/{self.name}', 'event_out'), io_event.serialize())

    def __write_data_config(self):
        with self.data_config_path.open('w') as f:
            f.write(self.data_config.serialize(indent=2))

    def __cb_ping(self, data: bytes) -> str | bytes:
        return 'pong'.encode('utf-8')

    def __cb_config_event(self, data: bytes) -> str | bytes:
        try:
            config_event: ModuleConfigEvent = ModuleConfigEvent.deserialize(data)
            self.module.command_config_event(config_event.cfg_key)
            return ModuleConfigEventReply(status=Status(error=False)).serialize()
        except Exception as e:
            self.__logger.error(f'__cb_config_event ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return ModuleConfigEventReply(
                status=Status(error=True, title=type(e).__name__, message=str(e))).serialize()

    def __cb_config(self, data: bytes) -> str | bytes:
        try:
            logger = logging.getLogger('__cb_config')
            message = ModuleConfigQuery.deserialize(data)
            logger.debug('rx: %s', message.serialize())

            if message.cmd == ModuleConfigQueryCmd.SET:
                try:
                    new_cfg: Dict = json.loads(message.cfg_json)
                except json.decoder.JSONDecodeError:
                    logger.error(f'set: JSON decoding failed: {message.cfg_json}')
                    reply = ModuleConfigReply(status=Status(error=True, title='JSON decoding failed', message=''))
                    return reply.serialize()

                # update missing fields + remove non-existing
                default = self.config_handler.get_default_config()
                for k, v in default.items():
                    if k not in new_cfg:
                        new_cfg[k] = v
                for k, v in new_cfg.items():
                    if k not in default:
                        new_cfg.pop(k)
                        logger.warning(f'removed invalid key: {k} with value {v}')

                # validate new config via json-schema
                if not self.config_handler.valid(new_cfg):
                    logger.error(f'invalid config (schema): {new_cfg}')
                    reply = ModuleConfigReply(status=Status(error=True, title='invalid config',
                                                            message='schema validation failed'))
                    return reply.serialize()

                # let module validate config
                validation_status = self.module.command_validate_config(new_cfg)
                if validation_status.error:
                    logger.error(f'invalid config (module): {new_cfg}')
                    reply = ModuleConfigReply(status=validation_status)
                    return reply.serialize()

                # save config to disk
                self.config_handler.write_config(new_cfg)

                # apply config in module
                status = self.module.command_apply_config()
                self.data_broker.notify_possible_schema_change()

                reply = ModuleConfigReply(status=status)
                return reply.serialize()

            elif message.cmd == ModuleConfigQueryCmd.GET:
                reply = ModuleConfigReply(status=Status(error=False), cfg_json=self.config_handler.config_json())
                return reply.serialize()

            elif message.cmd == ModuleConfigQueryCmd.GET_DEFAULT:
                reply = ModuleConfigReply(status=Status(error=False), cfg_json=self.config_handler.get_default_json())
                return reply.serialize()

            else:
                logger.error('unknown command: %s', message.cmd.name)
                reply = ModuleConfigReply(status=Status(error=True, title='unknown command',
                                                        message=message.cmd.name))
                return reply.serialize()

        except Exception as e:
            self.__logger.error(f'__cb_config ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return ModuleConfigReply(
                status=Status(error=True, title=type(e).__name__, message=str(e))).serialize()

    def __cb_data_config(self, data: bytes) -> str | bytes:
        try:
            logger = logging.getLogger('__cb_data_config')
            message: ModuleDataConfigQuery = ModuleDataConfigQuery.deserialize(data)
            logger.debug('rx: %s', message.serialize())

            if message.cmd == ModuleDataConfigCmd.GET:
                return ModuleDataConfigReply(status=Status(error=False), config=self.data_config).serialize()
            elif message.cmd == ModuleDataConfigCmd.SET:
                self.data_broker.configure_live(message.module_data_config)
                self.data_config = ModuleDataConfig.from_dict(message.module_data_config.get_dict())
                # save to data_config.json
                self.__write_data_config()
                return ModuleDataConfigReply(status=Status(error=False)).serialize()
            else:
                logger.error('unknown command: %s', message.cmd.name)
                return ModuleDataConfigReply(
                    status=Status(error=True, title='unknown command', message=message.cmd.name)).serialize()

        except Exception as e:
            self.__logger.error(f'__cb_data_config ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return ModuleDataConfigReply(
                status=Status(error=True, title=type(e).__name__, message=str(e))).serialize()

    def __cb_prepare_sampling(self, data: bytes) -> str | bytes:
        try:
            logger = logging.getLogger('__cb_prepare_sampling')
            message: StartStop = StartStop.deserialize(data)
            logger.debug('rx: %s', message.serialize())

            if message.cmd == StartStopCmd.START:
                if self.state.state == MeasurementStateType.IDLE:
                    logger.debug('prepare sampling')
                    self.module.command_prepare_sampling()
                    self.state.state = MeasurementStateType.PREPARE_SAMPLING
                else:
                    logger.warning('sampling already active')
            else:
                raise ValueError(f'Unknown command: {message.cmd.name}')

            # reply OK
            return StartStopReply(status=Status(error=False)).serialize()
        except Exception as e:
            self.__logger.error(f'__cb_prepare_sampling ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return StartStopReply(status=Status(error=True, title=type(e).__name__, message=str(e))).serialize()

    def __cb_sub_start_sampling(self, key: str, data: bytes) -> None:
        try:
            logger = logging.getLogger('__cb_sub_sampling')
            message: StartStop = StartStop.deserialize(data)
            logger.debug('rx %s: %s', key, message.serialize())

            if message.cmd == StartStopCmd.START:
                if self.state.state == MeasurementStateType.IDLE:
                    logger.error('start called with wrong state: %s', self.state.state.name)
                    return
                if self.state.state == MeasurementStateType.PREPARE_SAMPLING:
                    logger.debug('start sampling')
                    self.module.command_start_sampling()
                    self.state.state = MeasurementStateType.SAMPLING
                    self._sampling_active = True
                else:
                    logger.info('no need to start sampling in state %s', str(self.state.state))
            else:
                raise ValueError(f'Unknown command for {str(key)}: {message.cmd.name}')
        except Exception as e:
            self.__logger.error(f'__cb_sub_sampling ({type(e).__name__}): {e}\n{traceback.format_exc()}')

    def __cb_stop_sampling(self, data: bytes) -> str | bytes:
        try:
            logger = logging.getLogger('__cb_stop_sampling')
            message: StartStop = StartStop.deserialize(data)
            logger.debug('rx: %s', message.serialize())

            if message.cmd == StartStopCmd.STOP:
                logger.debug('stop sampling')
                self.module.command_stop_sampling()
                self.state.state = MeasurementStateType.IDLE
                self._sampling_active = False
            else:
                raise ValueError(f'Unknown command: {message.cmd.name}')

            # reply OK
            return StartStopReply(status=Status(error=False)).serialize()
        except Exception as e:
            self.__logger.error(f'__cb_stop_sampling ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return StartStopReply(status=Status(error=True, title=type(e).__name__, message=str(e))).serialize()

    def __cb_prepare_capture(self, data: bytes) -> str | bytes:
        try:
            logger = logging.getLogger('__cb_prepare_capture')
            message: MeasurementInfo = MeasurementInfo.deserialize(data)
            logger.debug('rx: %s', message.serialize())

            # check if we are already capturing
            if self.state.state == MeasurementStateType.CAPTURING:
                logger.warning('prepare called with capturing already active')
                return Status(error=True, title='prepare capture failed',
                              message='capturing already active').serialize()

            if message.name == '':
                logger.error('no measurement name given')
                return Status(error=True, title='prepare capture failed',
                              message='no measurement name given').serialize()

            # save measurement infos
            self.state.measurement_info = MeasurementInfo.from_dict(message.get_dict())

            if self.data_config.enable_capturing \
                    or self.data_config.enable_live_all_samples \
                    or self.data_config.enable_live_fixed_rate:
                # check if sampling is already enabled
                if self.state.state != MeasurementStateType.SAMPLING:
                    logger.debug('prepare and start sampling')
                    self.module.command_prepare_sampling()
                    self.state.state = MeasurementStateType.PREPARE_SAMPLING
                    self.module.command_start_sampling()
                    self.state.state = MeasurementStateType.SAMPLING
                else:
                    logger.debug('sampling already active')

            # make sure directory exists in any case
            create_directory(Path(self.data_broker.get_module_data_dir(message.name)))

            if self.data_config.enable_capturing:
                self.module.command_prepare_capturing()
                self.data_broker.prepare_capturing(message.name, data_schemas=self.module.command_get_schemas())
                self.state.state = MeasurementStateType.PREPARE_CAPTURING
            return Status(error=False).serialize()

        except Exception as e:
            self.__logger.error(f'__cb_prepare_capture ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return Status(error=True, title=type(e).__name__, message=str(e)).serialize()

    def __cb_sub_start_capture(self, key: str, data: bytes) -> None:
        try:
            logger = logging.getLogger('__cb_sub_capture')
            message = StartStop.deserialize(data)
            logger.debug('rx %s: %s', key, message.serialize())

            if message.cmd == StartStopCmd.START:
                if self.data_config.enable_capturing:
                    if self.state.state != MeasurementStateType.PREPARE_CAPTURING:
                        logger.error('start called with wrong state: %s', self.state.state.name)
                        return
                    if not self.data_broker.start_capturing():
                        self.module.command_start_capturing()
                        self.state.state = MeasurementStateType.CAPTURING
                else:
                    logger.debug('capturing is disabled')
            else:
                raise ValueError(f'Unknown command for {str(key)}: {message.cmd.name}')

            # write meta-data to .json file
            if self.state.measurement_info.name != '' and self.data_config.enable_capturing:
                meta = self.module.get_meta_data()
                config = self.config_handler.config
                additional_meta_data = [("config", json.dumps(config)),
                                        ("module_type", self.config_handler.type),
                                        ("module_name", self.name)]
                for key, value in additional_meta_data:
                    if key in meta:
                        logger.error(f'Key "{key}" already stored in meta-data! Value: {meta[key]}')
                    else:
                        meta.update({key: value})

                try:
                    file_path: Path = self.data_dir / self.state.measurement_info.name / self.name / "module_meta.json"
                    with open(file_path, "w") as f:
                        logger.debug(f'Write meta-data JSON {file_path} to disk: {", ".join(meta.keys())}')
                        json.dump(meta, f, indent=2, ensure_ascii=False)
                except Exception as _e:
                    logger.error(f'write_metadata failed ({type(_e).__name__}): {_e}\n{traceback.format_exc()}')

            # reset the measurement name on stop
            if message.cmd == StartStopCmd.STOP:
                self.state.measurement_info = MeasurementInfo()
                #self.state.measurement_info.Clear()

        except Exception as e:
            self.__logger.error(f'__cb_sub_capture ({type(e).__name__}): {e}\n{traceback.format_exc()}')

    def __cb_stop_capture(self, data: bytes) -> str | bytes:
        try:
            logger = logging.getLogger('__cb_stop_capture')
            message: StartStop = StartStop.deserialize(data)
            logger.debug('rx: %s', message.serialize())

            if message.cmd == StartStopCmd.STOP:
                self.module.command_stop_capturing()
                if self._sampling_active:
                    logger.debug('keep sampling active')
                    self.state.state = MeasurementStateType.SAMPLING
                else:
                    logger.debug('stop sampling')
                    self.module.command_stop_sampling()
                    self.state.state = MeasurementStateType.IDLE
                self.data_broker.stop_capturing()
            else:
                raise ValueError(f'Unknown command: {message.cmd.name}')

            return StartStopReply(status=Status(error=False)).serialize()

        except Exception as e:
            self.__logger.error(f'__cb_stop_capture ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return StartStopReply(status=Status(error=True, title=type(e).__name__, message=str(e))).serialize()

    def __cb_get_latest(self, data: bytes) -> str | bytes:
        try:
            # logger = logging.getLogger('__cb_get_latest')
            # logger.debug('rx %s', key)

            time_ns, latest_data = self.data_broker.get_latest()
            if latest_data is not None:
                latest_data['ts'] = time_ns
                return orjson.dumps(latest_data)
            else:
                return "{}".encode('utf-8')
        except Exception as e:
            self.__logger.error(f'__cb_get_latest ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return "{}".encode('utf-8')

    def __cb_get_docu(self, data: bytes) -> str | bytes:
        message = DocumentationReply(html_text='')
        try:
            documentation_path = os.getcwd() + "/documentation.html"
            # make sure documentation file exists
            if not os.path.exists(documentation_path):
                self.__logger.error("Documentation file not found")
                message.html_text = "Documentation file not found."
            else:
                # read documentation file content into string
                with open(documentation_path, 'r') as file:
                    message.html_text = file.read()
        except Exception as e:
            self.__logger.error(f'_cb_get_docu ({type(e).__name__}): {e}\n{traceback.format_exc()}')

        return message.serialize()

    def __cb_get_metadata(self, data: bytes) -> str | bytes:
        try:
            metadata = self.module.get_meta_data()
            return orjson.dumps(metadata)
        except Exception as e:
            self.__logger.error(f'__cb_get_metadata ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return "{}".encode('utf-8')

    def __cb_get_schemas(self, data: bytes) -> str | bytes:
        try:
            schemas = self.module.command_get_schemas()
            schema_list = []
            for schema in schemas:
                if "topic" in schema:
                    schema_list.append(schema["topic"])
                else:
                    schema_list.append(self.module.name)
            return GetSchemasReply({"topic_names": schema_list}).serialize()
        except Exception as e:
            self.__logger.error(f'__cb_get_schemas ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return "{}".encode('utf-8')

    def __cb_sub_event(self, key: str, data: bytes) -> None:
        try:
            logger = logging.getLogger('__cb_event')
            message = IOEvent.deserialize(data)
            logger.debug('rx %s: %s', key, message.serialize())
            self.module.event_received(message)
        except Exception as e:
            self.__logger.error(f'__cb_event ({type(e).__name__}): {e}\n{traceback.format_exc()}')


def main(module: Type[IOModule], config_type: Type[BaseConfig], module_name: str) -> None:
    # set UTC timezone
    os.environ['TZ'] = 'UTC'
    time.tzset()

    # preload these modules in all multiprocessing processes created using forkserver
    multiprocessing.set_forkserver_preload(['multiprocessing', 'threading', 'logging', 'time', 'os', 'json', 'queue',
                                            'signal', 'traceback'])
    multiprocessing.set_start_method('forkserver')  # 'forkserver' / 'spawn'

    LoggerMixin.configure_logger(level=os.getenv('LOGLEVEL'))
    logger_main = logging.getLogger('IOModule main')
    shutdown_ev = threading.Event()

    for sig in signal.valid_signals():
        try:
            signal.signal(sig, lambda signum, frame: log_reentrant(f'UNHANDLED signal {signum} called'))
        except OSError:
            pass

    # ignore child signal
    signal.signal(signal.SIGCHLD, lambda signum, frame: log_reentrant(f'ignoring signal {signum}'))

    # handle shutdown signals
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda signum, frame: (shutdown_ev.set(),
                                                  log_reentrant(f'signal {signum} called -> shutdown!')))

    module_interface = None
    try:
        module_interface = ModuleInterface(io_module_type=module, config_type=config_type,
                                           shutdown_event=shutdown_ev, module_name=module_name)
        module_interface.prepare()
    except Exception as e_main:
        logger_main.error(f'IOModule died tragically on creation: {type(e_main).__name__}: {e_main}\n'
                          f'{traceback.format_exc()}')
        if module_interface is not None:
            module_interface.teardown()
        exit(1)

    try:
        if not shutdown_ev.is_set():
            module_interface.module.start()
            module_interface.module.command_apply_config()
            module_interface.module.data_broker.notify_possible_schema_change()
        if not shutdown_ev.is_set():
            module_interface.register()
    except Exception as e_main:
        logger_main.error(f'IOModule died tragically during start: {type(e_main).__name__}: {e_main}\n'
                          f'{traceback.format_exc()}')
    else:
        shutdown_ev.wait()
    shutdown_ev.set()
    module_interface.teardown()

    num_threads_left = threading.active_count() - 1
    logger_main.debug(f'done - return code {module_interface.exit_return_value} - threads left: {num_threads_left}')
    if num_threads_left > 0:
        logger_main.info(f'threads left: {[thread.name for thread in threading.enumerate()]}')

    exit(module_interface.exit_return_value)
