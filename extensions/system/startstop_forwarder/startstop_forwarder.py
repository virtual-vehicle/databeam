"""
Start/stop Signal Forwarder to external DataBeam
"""
import logging
import threading
import traceback
from typing import Dict
from concurrent.futures import ThreadPoolExecutor

import environ

from vif.data_interface.connection_manager_zmq import Key
from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.data_interface.helpers import ping_controller
from vif.data_interface.network_messages import Status, StartStop, StartStopCmd, MeasurementInfo, MeasurementStateType

from system.startstop_forwarder.config import StartstopForwarderConfig


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='StartStopForwarder')


class StartStopForwarder(IOModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME
        self.data_broker.capabilities.capture_data = False
        self.data_broker.capabilities.live_data = False

        self.followers_db_ids = []

    def start(self):
        self.logger.debug('starting')

    def stop(self):
        self.logger.info('module closed')

    def command_validate_config(self, config: Dict) -> Status:
        return Status(error=False)

    def _prepare_connections_worker(self):
        logger = logging.getLogger('prepare_connections')
        # add external router connections by pinging once
        for db in self.followers_db_ids:
            try:
                logger.info('pinging follower: ' + db)
                ret = ping_controller(self.module_interface.cm, db_id=db,
                                      module_name=f'{self.module_interface.db_id}/m/{self.name}', timeout=0.5)
                if ret is False:
                    logger.warning('ping failed for follower: ' + db)
                else:
                    logger.info('ping success for follower: ' + db)
            except Exception as e:
                logger.error(f'EX pinging follower {db}: {type(e).__name__}: {e}\n{traceback.format_exc()}')

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            self.followers_db_ids = []
            known_db_ids = self.module_interface.cm.get_external_databeam_ids()
            # verify that all configured DBIDs are actually registered.
            # send warning for unconfigured and remove from list
            for dbid in config['follower_db_ids']:
                if dbid not in known_db_ids:
                    self.module_interface.log_gui('unknown follower DBID: ' + dbid, logging.WARNING)
                else:
                    self.followers_db_ids.append(dbid)

            # do not wait for router-connection-preparation - might take a few 100 ms
            threading.Thread(target=self._prepare_connections_worker, daemon=True).start()
            return Status(error=False)

        except Exception as e:
            self.logger.error(f'error applying config: {type(e).__name__}: {e}\n{traceback.format_exc()}')
            return Status(error=True, title=type(e).__name__, message=str(e))

    def _send_cmd(self, cmd_type: MeasurementStateType, start_stop_cmd: StartStopCmd, timeout: float):
        if cmd_type == MeasurementStateType.SAMPLING:
            cmd_type_str = 'cmd_sampling'
        elif cmd_type == MeasurementStateType.CAPTURING:
            cmd_type_str = 'cmd_capture'
        else:
            self.logger.error('wrong cmd_type: ' + cmd_type.name)
            return

        # forward message (fire and forget) to all following DataBeams
        if len(self.followers_db_ids) > 0:
            if cmd_type == MeasurementStateType.CAPTURING and start_stop_cmd == StartStopCmd.START:
                data = StartStop(cmd=start_stop_cmd,
                                 measurement_info=MeasurementInfo.from_dict(
                                     self.module_interface.state.measurement_info.get_dict())
                                 ).serialize()
            else:
                data = StartStop(cmd=start_stop_cmd).serialize()
            self.logger.info('sending %s / %s to %s', cmd_type_str, data, self.followers_db_ids)
            data = data.encode()

            follower_db_executor = ThreadPoolExecutor(max_workers=len(self.followers_db_ids),
                                                      thread_name_prefix=cmd_type_str)
            for dbid in self.followers_db_ids:
                self.logger.debug('sending %s / %s to %s', cmd_type_str, start_stop_cmd.name, dbid)
                follower_db_executor.submit(self.module_interface.cm.request,
                                            key=Key(dbid, 'c', cmd_type_str), data=data, timeout=timeout)
            follower_db_executor.shutdown(wait=True)
            self.logger.debug('done sending.')

    def command_state_change(self, command: StartStopCmd, related_state: MeasurementStateType) -> None:
        if not self.module_interface.shutdown_ev.is_set():
            self.logger.info('state change! %s / %s', related_state.name, command.name)
            self._send_cmd(related_state, command, timeout=(2 - 0.5) if command == StartStopCmd.START else (5 - 0.5))


if __name__ == '__main__':
    main(StartStopForwarder, StartstopForwarderConfig, environ.to_config(ModuleEnv).MODULE_NAME)
