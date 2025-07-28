"""
The core controller of DataBeam. Handles module registration, as well as start/stop of sampling and capturing.
Also manages GUI messages with the help of the JobServer class.
"""

import json
import logging
import os
import queue
import signal
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from io import IOBase
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Tuple, Callable, List, Optional

import environ
import zmq

from vif.logger.logger import LoggerMixin, log_reentrant
from vif.file_helpers.creation import create_directory
from vif.file_helpers.filename import get_valid_filename
from vif.data_interface.connection_manager import ConnectionManager, Key
from vif.asyncio_helpers.asyncio_helpers import tick_generator
from vif.jobs.job_entry import StateJob, EventJob, LogJob
from vif.zmq.helpers import create_bind
from vif.data_interface.network_messages import (Reply, MeasurementState, ModuleRegistryQuery,
                                                 ModuleRegistryReply, Module, SystemControlQuery, SystemControlReply,
                                                 Status, StartStop, StartStopReply, MetaDataQuery, MetaDataReply,
                                                 MeasurementStateType, StartStopCmd, ModuleRegistryQueryCmd,
                                                 SystemControlQueryCmd, MetaDataQueryCmd, ExternalDataBeamQueryReply)
from vif.data_interface.helpers import check_leftover_threads
from vif.plot_juggler.plot_juggler_writer import PlotJugglerWriter

from meta_handler import MetaHandler
from job_server import JobServer
from mcap_recover import recover_unfinalized_mcaps, fix_unfinished_measurements_meta


@environ.config(prefix='')
class ControllerEnv:
    LOGLEVEL = environ.var(help='logging level', default='DEBUG')
    CONFIG_DIR = environ.var(help='config root directory', converter=lambda x: Path(x).expanduser())
    DATA_DIR = environ.var(help='data directory', converter=lambda x: Path(x).expanduser())
    DEPLOY_VERSION = environ.var(help='docker images tag', default='latest')
    DB_ID = environ.var(help='DataBeam domain name for communication')
    HOST_NAME_FILE = environ.var(help='fake hostname file', default='/etc/hostname')
    DB_ROUTER = environ.var(help='DataBeam router hostname to find other nodes', default='localhost')
    DBID_LIST = environ.var(help='comma-separated list of DataBeam id/hostname', default='')


class Messages:
    MSG_MEASURE_ACTIVE = 'Measurement Active'
    MSG_SAMPLING_ACTIVE = 'Sampling Active'


class Controller(LoggerMixin):
    def __init__(self, cfg: ControllerEnv, shutdown_ev: threading.Event):
        super().__init__()

        self._deploy_version: str = cfg.DEPLOY_VERSION
        self.logger.info(f'DEPLOY_VERSION: {self._deploy_version}')
        self._db_id: str = cfg.DB_ID
        assert len(self._db_id) > 0, 'DB_ID environment variable not set'
        self.logger.info(f'DB_ID: {self._db_id}')

        self._shutdown_event: threading.Event = shutdown_ev
        self._healthcheck_socket = None

        # assign and create directory structure
        self._config_dir: Path = cfg.CONFIG_DIR / cfg.DEPLOY_VERSION / 'controller'
        create_directory(Path(self._config_dir))

        self._data_dir: Path = cfg.DATA_DIR / cfg.DEPLOY_VERSION  # will be followed by a directory "measurement_name"
        create_directory(Path(self._data_dir))

        # try to load host name
        self._hostname: str = 'unset'
        try:
            with open(cfg.HOST_NAME_FILE) as f:
                self._hostname = f.readline().strip()
                self.logger.info(f'hostname: {self._hostname}')
        except Exception as e:
            self.logger.error(f'opening hostname file failed ({type(e).__name__}): {e}')

        self._state_lock: threading.Lock = threading.Lock()
        self._state: MeasurementState = MeasurementState(state=MeasurementStateType.IDLE)
        self._sampling_active: bool = False

        # register external dbid's if configured
        self._db_id_hostnames = {}
        for db in cfg.DBID_LIST.strip('"').split(','):
            # format: dbid/hostname.domain:pub_port
            if len(db) > 0:
                try:
                    dbid, hostname = db.split('/')
                    if len(dbid) == 0 or len(hostname) == 0:
                        raise ValueError
                    self._db_id_hostnames[dbid] = hostname
                    self.logger.info('registering external dbid: %s (%s)', dbid, hostname)
                except ValueError:
                    self.logger.warning(f'invalid dbid_list entry: {db}')
                    continue

        self._cm: ConnectionManager = ConnectionManager(router_hostname=cfg.DB_ROUTER,
                                                        db_id=self._db_id, node_name='c',
                                                        shutdown_event=shutdown_ev,
                                                        max_parallel_req=5,  # diminishing returns for more than ~3
                                                        # TODO how many? create dynamically with num. modules .. or s/t
                                                        max_parallel_queryables=10)
        self._cm.set_external_databeams(list(self._db_id_hostnames.keys()), list(self._db_id_hostnames.values()))

        self._pub_topics: Dict[str, Key] = {
            'capture': Key(self._db_id, 'c', 'bc/start_capture'),
            'sampling': Key(self._db_id, 'c', 'bc/start_sampling')
        }

        # create module registry lock
        self._register_lock: threading.Lock = threading.Lock()
        # module registry: name: module
        self._module_registry: Dict[str, Module] = {}
        self._module_ts: Dict[str, float] = {}
        self._registry_watchdog: threading.Thread = threading.Thread(target=self._registry_timed_watchdog_worker,
                                                                     name='registry_watchdog')

        self._async_cmd_queue: queue.Queue[Tuple[float, Callable[[], None]]] = queue.Queue()
        self._async_cmd_thread = threading.Thread(target=self._async_cmd_worker, name='async_cmd_thread')

        self.meta_handler: MetaHandler = MetaHandler(config_dir=self._config_dir, hostname=self._hostname,
                                                     db_id=self._db_id, deploy_version=self._deploy_version)

        self._job_server: JobServer = JobServer(cm=self._cm, db_id=self._db_id)

        # create state job
        self._state_job: StateJob = StateJob(self._cm, self._db_id)
        self._job_server.add(self._state_job)

        # create plot juggler writer
        self._plot_juggler_writer: PlotJugglerWriter = PlotJugglerWriter(self._data_dir)

    def log_gui(self, message: str, log_severity=logging.DEBUG) -> None:
        """
        Uses the JobServer to show a message on the WebGUI.
        """
        if log_severity > logging.NOTSET:
            self.logger.log(log_severity, "log_gui: %s", message)
        time_ns = datetime.now(timezone.utc)
        time_str = time_ns.strftime("%H:%M:%S.%f")
        log_job = LogJob(self._cm, self._db_id)
        log_job.set_name("Controller").set_message(message).set_time(time_str).set_done()
        self._job_server.add(log_job)

    def start(self):
        """
        Starts up the controller by setting up publishers for capturing/sampling and by
        registering callbacks for all receivable queries.
        """
        self.logger.info('searching data directory for unfinished measurements')
        recover_unfinalized_mcaps(self._data_dir)
        fix_unfinished_measurements_meta(self._data_dir)

        self.logger.info('starting controller')
        try:
            self._job_server.start()

            # register all broadcasts / publishers
            for topic in self._pub_topics.values():
                self._cm.declare_publisher(topic)

            self._registry_watchdog.start()
            self._async_cmd_thread.start()

            # register all incoming queryables
            for key, cb in [(Key(self._db_id, 'c', 'module_registry'), self._cb_qry_module_registry),
                            (Key(self._db_id, 'c', 'system_control'), self._cb_qry_sys_control),
                            (Key(self._db_id, 'c', 'cmd_sampling'), self._cb_qry_cmd_sampling),
                            (Key(self._db_id, 'c', 'cmd_capture'), self._cb_qry_cmd_capture),
                            (Key(self._db_id, 'c', 'get_state'), self._cb_qry_get_state),
                            (Key(self._db_id, 'c', 'metadata'), self._cb_qry_metadata),
                            (Key(self._db_id, 'c', 'databeam_registry'), self._cb_qry_databeam_registry)
                            ]:
                self._cm.declare_queryable(key, cb)

            self._shutdown_event.wait(0.5)
            self._cm.declare_queryable(Key(self._db_id, 'c', 'ping'), self._cb_qry_ping)

            # open a dummy socket for docker to be able to perform a healthcheck
            self._healthcheck_socket = create_bind('tcp://*:1100', zmq, zmq.PUSH)

        except Exception as e:
            self.logger.error(f'start failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            raise e

    def stop(self):
        """
        Stops the controller.
        """
        self.logger.info('stopping controller')
        self._shutdown_event.set()

        # stop watchdog
        if self._registry_watchdog.is_alive():
            self._registry_watchdog.join()
            self.logger.debug('watchdog joined')

        # stop async cmd thread
        if self._async_cmd_thread.is_alive():
            self._async_cmd_thread.join()
            self.logger.debug('async_cmd_thread joined')

        # stop running measurement (if running)
        if self._state.state == MeasurementStateType.CAPTURING:
            try:
                self.logger.info('stopping capturing')
                reply = self._cm.request(Key(self._db_id, 'c', 'cmd_capture'),
                                         StartStop(cmd=StartStopCmd.STOP).serialize())
                if reply is None:
                    raise RuntimeError('stop capturing failed (no reply)')
                message = StartStopReply.deserialize(reply)
                if message.status.error:
                    self.logger.error(f'{message.status.title}: {message.status.message}')
                else:
                    self.logger.info('stop capturing OK')
            except Exception as e:
                self.logger.error(f'stop capturing failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')

        try:
            self._job_server.stop()
            self._cm.close()
            self.logger.info('stop done')
        except Exception as e:
            self.logger.error(f'stop failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')

    def _registry_timed_watchdog_worker(self):
        """
        Checks for every module if it sent a heartbeat in a certain time interval. If not,
        it removes the module from its registry.
        """
        logger = logging.getLogger('registry_timed_watchdog')
        logger.info('thread started')

        heartbeat_interval_s = 2.5
        g = tick_generator(heartbeat_interval_s, drop_missed=True, time_source=time.time)

        while not self._shutdown_event.is_set():
            #logger.debug("Check for inactive registered modules.")

            with self._register_lock:
                # get current time
                now = time.time()

                # true if any module has been removed
                any_module_removed = False

                # remove modules based on last receive register time
                for module, ts in self._module_ts.items():
                    dt = now - ts

                    if dt > heartbeat_interval_s:
                        # remove module from registry
                        logger.info('Removing %s from registry due to timeout', module)
                        self._module_registry.pop(module)
                        any_module_removed = True

                if any_module_removed:
                    self._module_ts = {k: v for k, v in self._module_ts.items() if k in self._module_registry.keys()}

                    # inform REST-API that modules changed
                    event_job = EventJob(self._cm, self._db_id)
                    event_job.set_modules_changed(True).set_done()
                    self._job_server.add(event_job)
                    self._job_server.update()

            # wait for timeout or killed thread
            self._shutdown_event.wait(timeout=next(g))

    def _add_async_cmd(self, cmd: Callable[[], None], timeout_s: float = 0):
        # add command to async cmd queue with defined deadline in the future
        self._async_cmd_queue.put((time.time() + timeout_s, cmd))

    def _async_cmd_worker(self):
        logger = logging.getLogger('async_cmd_worker')
        logger.info('thread started')

        cmds: List[Tuple[float, Callable[[], None]]] = []
        next_deadline = float("inf")

        while not self._shutdown_event.is_set():
            try:
                # limit wait time to max. 200ms and min. 10ms
                wait_time = max(min(next_deadline - time.time(), 0.2), 0.01)
                try:
                    deadline, cmd = self._async_cmd_queue.get(timeout=wait_time)
                    # add new command and sort list by deadline
                    cmds.append((deadline, cmd))
                    cmds.sort(key=lambda tup: tup[0], reverse=True)
                except queue.Empty:
                    if len(cmds) == 0:
                        continue

                now = time.time()
                # iterate over reversed list and execute / pop commands with earliest deadline first
                for index, c in reversed(list(enumerate(cmds))):
                    deadline, cmd = c
                    if deadline <= now:
                        cmd()
                        cmds.pop(index)
                        next_deadline = float("inf")
                    else:
                        if deadline < next_deadline:
                            next_deadline = deadline
            except Exception as e:
                logger.error(f'EX ({type(e).__name__}): {e}\n{traceback.format_exc()}')

    def _async_module_start_cmd(self, module_name):
        logger = logging.getLogger('_async_module_start_cmd')
        with self._state_lock:
            if (self._state.state == MeasurementStateType.CAPTURING or
                    self._state.state == MeasurementStateType.SAMPLING):
                # prepare capture/sampling on module (wait for reply)
                if self._state.state == MeasurementStateType.CAPTURING:
                    cmd_string = 'capture'
                    cmd_payload = self._state.measurement_info.serialize()
                else:
                    cmd_string = 'sampling'
                    cmd_payload = StartStop(cmd=StartStopCmd.START).serialize()
                logger.info(f'start {cmd_string} on newly added module')
                try:
                    reply = self._cm.request(Key(self._db_id, f'm/{module_name}', f'prepare_{cmd_string}'), cmd_payload)
                    if reply is not None:
                        # start capture/sampling on module (broadcast)
                        self._cm.publish(self._pub_topics[cmd_string], StartStop(cmd=StartStopCmd.START).serialize())
                except StopIteration:
                    logger.error(f'start {cmd_string}: no response from module')
                except Exception as e:
                    logger.error(f'start failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')

    def _async_module_list_changed(self):
        event_job = EventJob(self._cm, self._db_id)
        event_job.set_modules_changed(True).set_done()
        self._job_server.add(event_job)
        self._job_server.update()

    def _cb_qry_module_registry(self, data: bytes) -> str | bytes:
        """
        Uses the ModuleRegistryQuery to perform following tasks upon query:
            - Register module
            - Remove module
            - List all modules in registry
        """
        try:
            logger = logging.getLogger('_cb_qry_module_registry')
            message = ModuleRegistryQuery.deserialize(data)

            # do not print info for every module register "heartbeat"
            if message.cmd != ModuleRegistryQueryCmd.REGISTER:
                logger.debug('rx: %s', message.serialize())

            with self._register_lock:
                if message.cmd == ModuleRegistryQueryCmd.REGISTER:
                    already_registered = message.module.name in self._module_registry

                    if not already_registered:
                        logger.info('rx: %s', message.serialize())
                        logger.info('Registering new module: %s', message.module.name)

                    # register (new) module
                    self._module_registry[message.module.name] = message.module
                    self._module_ts[message.module.name] = time.time()

                    if not already_registered:
                        self._add_async_cmd(self._async_module_list_changed, 0.01)
                        # on startup: check controller state and start sampling / capturing immediately
                        self._add_async_cmd(partial(self._async_module_start_cmd, message.module.name), 0.1)

                        # reply to module (error=False if module is newly registered)
                        return ModuleRegistryReply(status=Status(error=False)).serialize()
                    else:
                        # reply the refresh was OK
                        return ModuleRegistryReply(
                            status=Status(error=True, title=message.module.name,
                                          message='already registered, updated watchdog')).serialize()


                elif message.cmd == ModuleRegistryQueryCmd.REMOVE:
                    logger.info('removing %s', message.module.name)
                    try:
                        self._module_registry.pop(message.module.name)
                        self._module_ts.pop(message.module.name)
                        self._add_async_cmd(self._async_module_list_changed, 0.01)
                    except KeyError:
                        logger.warning(f'trying to remove unknown module {message.module.name}')
                        return ModuleRegistryReply(status=Status(error=True, title='Name Error',
                                                                 message='trying to remove unknown module '
                                                                         f'{message.module.name}')).serialize()
                    else:
                        return ModuleRegistryReply(status=Status(error=False)).serialize()

                elif message.cmd == ModuleRegistryQueryCmd.LIST:
                    reply = ModuleRegistryReply(status=Status(error=False),
                                                modules=list(self._module_registry.values()))
                    logger.info('listing: %s', reply.serialize())
                    return reply.serialize()

                else:
                    logger.error('unknown command: %s', message.cmd.name)
                    return ModuleRegistryReply(
                        status=Status(error=True, title='unknown command', message=message.cmd.name)).serialize()

        except Exception as e:
            self.logger.error(f'_cb_qry_module_registry ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return ModuleRegistryReply(
                status=Status(error=True, title=type(e).__name__, message=str(e))).serialize()

    def _cb_qry_sys_control(self, data: bytes) -> str | bytes:
        """
        Uses the SystemControlQuery to perform following tasks upon query:
            - Restart docker
            - Docker pull
            - Shutdown system
            - Reboot system
            - Sync time
        """
        try:
            logger = logging.getLogger('_cb_qry_sys_control')
            message = SystemControlQuery.deserialize(data)
            logger.debug('rx: %s', message.serialize())

            if message.cmd in [SystemControlQueryCmd.SHUTDOWN,
                               SystemControlQueryCmd.REBOOT,
                               SystemControlQueryCmd.DOCKER_RESTART,
                               SystemControlQueryCmd.DOCKER_PULL,
                               SystemControlQueryCmd.SYNC_TIME]:
                logger.info('%s', message.cmd.name)

                try:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.connect("/tmp/databeam_hostcmd.sock")
                    if message.cmd == SystemControlQueryCmd.SHUTDOWN:
                        sock.send(b"dotheshutdown")
                        logger.info('host shutdown initiated')
                    elif message.cmd == SystemControlQueryCmd.REBOOT:
                        sock.send(b"dothereboot")
                        logger.info('host reboot initiated')
                    elif message.cmd == SystemControlQueryCmd.DOCKER_RESTART:
                        sock.send(b"dothedockerrestart")
                        logger.info('Docker restart initiated')
                    elif message.cmd == SystemControlQueryCmd.DOCKER_PULL:
                        sock.send(b"dothedockerpull")
                        logger.info('Docker pull initiated')
                    elif message.cmd == SystemControlQueryCmd.SYNC_TIME:
                        sock.send(f"dothetimesync#{message.target_iso_time}".encode())
                        logger.info(f'time synchronization initiated')
                    else:
                        raise KeyError(f'SystemControlQuery.Command not implemented: {message.cmd.name}')
                    return SystemControlReply(status=Status(error=False)).serialize()
                except Exception as e:
                    logger.error(f'host command failed: {type(e).__name__}: {e}')
                    return SystemControlReply(
                        status=Status(error=True, title=type(e).__name__, message=str(e))).serialize()
            else:
                raise KeyError(f'Unknown SystemControlQuery.Command: {message.cmd.name}')

        except Exception as e:
            self.logger.error(f'_cb_qry_sys_control ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return SystemControlReply(status=Status(error=True, title=type(e).__name__, message=str(e))).serialize()

    @staticmethod
    def error_ret_startstop(is_error: bool, title: Optional[str] = None, msg: Optional[str] = None) -> str | bytes:
        _status = Status(error=is_error)
        if title is not None:
            _status.title = title
        if msg is not None:
            _status.message = msg
        # reply to q.selector since the queryable (key) is a wildcard
        return StartStopReply(status=_status).serialize()

    def _cb_qry_cmd_sampling(self, data: bytes) -> str | bytes:
        """
        Start / stop / restart sampling on all modules.
        :param data: Serialized StartStop message
        """
        try:
            logger = logging.getLogger('_cb_qry_cmd_sampling')
            message = StartStop.deserialize(data)
            logger.debug('rx: %s', message.serialize())

            if message.cmd not in [StartStopCmd.START, StartStopCmd.STOP, StartStopCmd.RESTART]:
                raise ValueError(f'Unknown command for _cb_qry_cmd_sampling: {message.cmd.name}')

            with self._state_lock:
                if self._state.state not in [MeasurementStateType.IDLE, MeasurementStateType.SAMPLING]:
                    logger.warning(f'sampling command called in wrong state {str(self._state.state)}')
                    return self.error_ret_startstop(is_error=True, title='c/cmd_sampling',
                                                    msg=f'sampling command called in wrong state '
                                                        f'{str(self._state.state)}')

                if message.cmd == StartStopCmd.STOP or message.cmd == StartStopCmd.RESTART:
                    logger.info('sending STOP sampling to modules')
                    self._query_all_modules('stop_sampling', StartStop(cmd=StartStopCmd.STOP).serialize(),
                                            reply_cls=StartStopReply, show_gui_warning=True, timeout=5)

                    if self._state.state == MeasurementStateType.SAMPLING:
                        self._state.state = MeasurementStateType.IDLE
                    self._sampling_active = False

                if message.cmd == StartStopCmd.START or message.cmd == StartStopCmd.RESTART:
                    logger.info('sending PREPARE sampling to modules')
                    self._query_all_modules('prepare_sampling', StartStop(cmd=StartStopCmd.START).serialize(),
                                            reply_cls=StartStopReply, show_gui_warning=True, timeout=2)

                    logger.info('publishing START sampling broadcast to modules')
                    self._cm.publish(self._pub_topics['sampling'], StartStop(cmd=StartStopCmd.START).serialize())

                    if self._state.state == MeasurementStateType.IDLE:
                        self._state.state = MeasurementStateType.SAMPLING
                    self._sampling_active = True

                # update state job
                self._state_job.set_sampling(self._sampling_active)
                self._job_server.update()

            # reply OK
            return StartStopReply(status=Status(error=False)).serialize()
        except Exception as e:
            self.logger.error(f'_cb_cmd ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return self.error_ret_startstop(is_error=True, title=type(e).__name__, msg=str(e))

    def _helper_start_capture(self, logger: logging.Logger, message: Optional[StartStop] = None
                              ) -> Optional[str | bytes]:
        assert self._state_lock.locked(), 'should be locked by _cb_qry_cmd_capture()'

        # ignore command if we are already capturing
        if self._state.state == MeasurementStateType.CAPTURING:
            logger.warning('capture start called during running measurement')
            return self.error_ret_startstop(is_error=True, title='c/cmd_capture',
                                            msg='capture start called during running measurement')

        # create name for measurement
        t_now = datetime.now(timezone.utc)
        # save string with millisecond precision and filesystem-friendly characters
        t_string = t_now.isoformat(sep='_', timespec='milliseconds').replace(':', '-').split('+')[0]

        # update and load meta-data
        self.meta_handler.update_dynamic_meta({
            'start_time_utc': t_now.isoformat(),
            'stop_time_utc': '',
            'duration': ''
        })
        meta_data = self.meta_handler.get_combined_meta()

        if message.measurement_info is not None:
            # set time string the same as remote measurement, but keep note of our true start time in meta-data
            # fetch time string from name of remote measurement_info (e.g., 2025-01-17_12-30-29.499_42_run_tag)
            t_string = '_'.join(message.measurement_info.name.split('_')[:2])

        self._state.measurement_info.name = get_valid_filename(
            f"{t_string}_{meta_data['run_id']}_{meta_data['run_tag']}", allow_unicode=False)
        self._state.measurement_info.run_id = int(meta_data['run_id'])
        self._state.measurement_info.run_tag = meta_data['run_tag']
        self._state.state = MeasurementStateType.CAPTURING

        logger.info(f'capture start called for {self._state.measurement_info.name}')

        # make sure directory structure exists
        create_directory(Path(self._data_dir / self._state.measurement_info.name))

        # write start meta-data
        self.write_metadata_file(meta_data)

        # prepare capture on all modules (wait for replies)
        logger.info('sending PREPARE capturing to modules')
        self._query_all_modules('prepare_capture', self._state.measurement_info.serialize(),
                                reply_cls=Status, show_gui_warning=True, timeout=2)

        # start capture on all modules (broadcast)
        logger.info('publishing START capturing to modules')
        self._cm.publish(self._pub_topics['capture'], StartStop(cmd=StartStopCmd.START).serialize())

        # write updated run meta (run_id)
        self.meta_handler.update_system_meta({'run_id': int(meta_data['run_id']) + 1})

        # update state job
        self._state_job.set_capture(True)
        self._state_job.set_sampling(True)
        self._job_server.update()

        # send event job to update files
        event_job = EventJob(self._cm, self._db_id)
        event_job.set_files_changed(True).set_meta_changed(True).set_done()
        self._job_server.add(event_job)
        self._job_server.update()
        return None

    def _helper_stop_capture(self, logger: logging.Logger) -> Optional[str | bytes]:
        assert self._state_lock.locked(), 'should be locked by _cb_qry_cmd_capture()'

        if self._state.state != MeasurementStateType.CAPTURING:
            logger.warning('capture stop called without running measurement')
            return self.error_ret_startstop(is_error=True, title='c/cmd_capture',
                                            msg='capture stop called without running measurement')

        t_now = datetime.now(timezone.utc)

        # create plotjuggler XML before modules write meta-data to avoid race-condition
        try:
            self._plot_juggler_writer.create_plot_juggler_xml(self._state.measurement_info.name)
        except Exception as e:
            logger.error(f'plotjuggler xml creation failed: {type(e).__name__}: {e}\n{traceback.format_exc()}')

        # notify all modules to stop capture
        stop_msg = StartStop(cmd=StartStopCmd.STOP).serialize()

        # stop capture on all modules (wait for replies)
        logger.info('sending STOP capturing to modules')
        self._query_all_modules('stop_capture', stop_msg, reply_cls=StartStopReply, show_gui_warning=True, timeout=5)

        # write stop meta-data
        try:
            meta_data = self.meta_handler.get_dynamic_meta()
            self.meta_handler.update_dynamic_meta({
                'stop_time_utc': t_now.isoformat(),
                'duration': str(t_now - datetime.fromisoformat(meta_data['start_time_utc']))
            })
            meta_data = self.meta_handler.get_combined_meta()
            # use most recent meta-data except for run_id and run_tag (use values from start-time)
            meta_data.update({'run_id': self._state.measurement_info.run_id,
                              'run_tag': self._state.measurement_info.run_tag})
            self.write_metadata_file(meta_data)

        except Exception as e:
            logger.error(f'meta-data update failed: {type(e).__name__}: {e}\n{traceback.format_exc()}')

        # check if we want to keep sampling (sampling is on)
        if self._sampling_active:
            self._state.state = MeasurementStateType.SAMPLING
        else:
            self._state.state = MeasurementStateType.IDLE
            # modules should know on their own to switch to sampling state

        # reset measurement info name
        self._state.measurement_info.name = ""

        # update state job
        self._state_job.set_capture(False)
        self._state_job.set_sampling(self._sampling_active)
        self._job_server.update()
        return None

    def _cb_qry_cmd_capture(self, data: bytes) -> str | bytes:
        try:
            logger = logging.getLogger('_cb_qry_cmd_capture')
            message = StartStop.deserialize(data)
            logger.debug('rx: %s', message.serialize())

            if message.cmd not in [StartStopCmd.START, StartStopCmd.STOP, StartStopCmd.RESTART]:
                raise ValueError(f'Unknown command for _cb_qry_cmd_capture: {message.cmd.name}')

            with self._state_lock:
                if message.cmd == StartStopCmd.STOP or message.cmd == StartStopCmd.RESTART:
                    if (ret := self._helper_stop_capture(logger)) is not None:
                        return ret

                if message.cmd == StartStopCmd.START or message.cmd == StartStopCmd.RESTART:
                    if (ret := self._helper_start_capture(logger, message)) is not None:
                        return ret

            # reply OK
            return StartStopReply(status=Status(error=False)).serialize()
        except Exception as e:
            self.logger.error(f'_cb_cmd ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return self.error_ret_startstop(is_error=True, title=type(e).__name__, msg=str(e))

    def _cb_qry_get_state(self, data: bytes) -> str | bytes:
        """
        Returns the current measurement state
        """
        try:
            logger = logging.getLogger('_cb_qry_get_state')
            logger.debug('rx')
            return self._state.serialize()
        except Exception as e:
            self.logger.error(f'_cb_qry_get_state ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return MeasurementState(state=MeasurementStateType.UNSPECIFIED).serialize()

    def _cb_qry_ping(self, data: bytes) -> str | bytes:
        """
        Receives a "ping" from a module and returns a "pong" to acknowledge connectivity.
        """
        logger = logging.getLogger('_cb_qry_ping')
        try:
            module_name = data.decode('utf-8')
        except:
            module_name = ''
        logger.debug('from %s', module_name if len(module_name) > 0 else '<unknown>')
        try:
            if len(module_name) == 0 or (len(module_name) > 0 and module_name in self._module_registry.keys()):
                return "pong".encode('utf-8')
        except Exception as e:
            self.logger.error(f'_cb_qry_ping ({type(e).__name__}): {e}\n{traceback.format_exc()}')
        logger.warning('rx <%s> but replied with "unknown"', module_name)
        return "pong_unknown".encode('utf-8')

    def _async_metadata_changed(self):
        event_job = EventJob(self._cm, self._db_id)
        event_job.set_meta_changed(True).set_done()
        self._job_server.add(event_job)
        self._job_server.update()

    def _cb_qry_metadata(self, data: bytes) -> str | bytes:
        """
        Uses the MetaDataQuery to perform the following tasks when called:
            - Get the current system meta-data
            - Add or modify some entries in the system or user meta-data
        """
        try:
            logger = logging.getLogger('_cb_qry_metadata')
            message = MetaDataQuery.deserialize(data)
            logger.debug('rx: %s', message.serialize())

            if message.cmd == MetaDataQueryCmd.GET:
                reply = MetaDataReply(status=Status(error=False),
                                      system_meta_json=json.dumps(self.meta_handler.get_system_meta()),
                                      user_meta_json=json.dumps(self.meta_handler.get_user_meta()))
                return reply.serialize()

            if message.cmd == MetaDataQueryCmd.SET:
                status = Status(error=False)

                if len(message.system_meta_json) > 0:
                    try:
                        self.meta_handler.update_system_meta(json.loads(message.system_meta_json))
                    except json.decoder.JSONDecodeError:
                        logger.error(f'JSON decode error (system_meta): {message.system_meta_json}')
                        status.error = True
                        status.title = 'System meta decode error '

                if len(message.user_meta_json) > 0:
                    try:
                        self.meta_handler.update_user_meta(json.loads(message.user_meta_json))
                    except json.decoder.JSONDecodeError:
                        logger.error(f'JSON decode error (user_meta): {message.user_meta_json}')
                        status.error = True
                        status.title += 'User meta decode error'

                # send meta-changed event
                self._add_async_cmd(self._async_metadata_changed, 0.01)

                return MetaDataReply(status=status).serialize()

            raise ValueError(f'Unknown command for _cb_qry_metadata: {message.cmd.name}')

        except Exception as e:
            self.logger.error(f'_cb_qry_metadata ({type(e).__name__}): {e}\n{traceback.format_exc()}')
            return MetaDataReply(status=Status(error=True, title=type(e).__name__, message=str(e))).serialize()

    def _cb_qry_databeam_registry(self, data: bytes) -> str | bytes:
        logger = logging.getLogger('_cb_qry_databeam_registry')
        try:
            logger.debug('rx: ExternalDataBeamQuery')
            db_id_list = list(self._db_id_hostnames.keys())
            hostname_list = list(self._db_id_hostnames.values())
            reply = ExternalDataBeamQueryReply(db_id_list, hostname_list)
            return reply.serialize()
        except Exception as e:
            logger.error(f'_cb_qry_databeam_registry ({type(e).__name__}): {e}\n{traceback.format_exc()}')
        return b''

    def _query_all_modules(self, cmd: str, payload: bytes | str, reply_cls: type[Reply],
                           show_gui_warning=False, timeout: int = 1) -> Tuple[Dict, List]:
        """
        Queries all registered modules with a given command and payload, collects their responses, and reports
        non-responding modules. Provides an optional GUI warning for modules that fail to respond.

        :param cmd: The command to be sent to each module.
        :param payload: The data payload to send along with the command.
        :param reply_cls: The class responsible for deserializing responses from the modules.
        :param show_gui_warning: Indicates whether to show a GUI warning for modules that do not respond.
        :param timeout: The timeout interval (in seconds) for a module's response. Defaults to 1s
        :returns: A tuple containing:
                - A dictionary mapping module names to their deserialized responses.
                - A list of all registered module names.
        """
        logger = logging.getLogger('_query_all_modules')
        # save status in responses with module name as key
        responses = {}
        all_modules = list(self._module_registry.keys())

        if len(all_modules) == 0:
            return responses, all_modules

        # send queries to each module
        logger.debug('cmd "%s" to %d modules', cmd, len(all_modules))
        t_start = time.time()
        with ThreadPoolExecutor(max_workers=len(all_modules)) as executor:
            future_to_module = {
                executor.submit(self._cm.request, Key(self._db_id, f'm/{m}', cmd), payload, timeout):
                    m for m in all_modules
            }
            for future in as_completed(future_to_module):
                try:
                    response = future.result()
                    if response is not None and len(response) > 0:  # None --> timeout, b'' not supported
                        responses[future_to_module[future]] = reply_cls.deserialize(response).get_dict()
                except Exception as e:
                    logger.warning(f'error from module "{future_to_module[future]}": ({type(e).__name__}): {e}\n'
                                   f'{traceback.format_exc()}')

        logger.debug('cmd "%s" took %.3fs - responses: %s', cmd, (time.time() - t_start), str(responses))
        # check if all registered modules answered
        for m in all_modules:
            if m not in responses.keys():
                if show_gui_warning:
                    self.log_gui(f'cmd "{cmd}": module "{m}" did not respond', logging.NOTSET)
                logger.warning(f'cmd "{cmd}": module "{m}" did not respond')
        return responses, all_modules

    def write_metadata_file(self, meta_data: Dict):
        """
        Writes the meta-data of the controller to a file.
        """
        try:
            file_path = self._data_dir / self._state.measurement_info.name / "meta.json"
            with open(file_path, "w") as f:  # type: IOBase
                self.logger.debug(f'Write meta-data JSON {file_path} to disk: {meta_data}')
                json.dump(meta_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f'write_metadata failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')


if __name__ == '__main__':
    # set UTC timezone
    os.environ['TZ'] = 'UTC'
    time.tzset()

    logger_main = logging.getLogger('controller main')

    # load environ config
    try:
        env_cfg = environ.to_config(ControllerEnv)
    except environ.MissingEnvValueError as e_main:
        logger_main.error('Missing environment variable: %s', e_main)
        exit(1)
    except Exception as e_main:
        logger_main.error(e_main)
        exit(1)

    # configure logging log level
    LoggerMixin.configure_logger(level=env_cfg.LOGLEVEL)

    for sig in signal.valid_signals():
        try:
            signal.signal(sig, lambda signum, frame: log_reentrant(f'UNHANDLED signal {signum} called'))
        except OSError:
            pass

    # ignore child signal
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)

    # handle shutdown signals
    shutdown_evt = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda signum, frame: (shutdown_evt.set(),
                                                  log_reentrant(f'signal {signum} called -> shutdown!')))
    try:
        controller = Controller(env_cfg, shutdown_evt)
    except Exception as e_main:
        logger_main.error(f'Controller died tragically on creation: {type(e_main).__name__}: {e_main}\n'
                          f'{traceback.format_exc()}')
        exit(1)

    try:
        controller.start()
    except Exception as e_main:
        logger_main.error(f'Controller died tragically during start: {type(e_main).__name__}: {e_main}\n'
                          f'{traceback.format_exc()}')
    else:
        shutdown_evt.wait()
    controller.stop()

    logger_main.debug(check_leftover_threads())
