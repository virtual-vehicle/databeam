"""
Autostart Module
"""
import threading
import traceback
from typing import Optional
import time
from datetime import datetime, timedelta

import environ

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.data_interface.network_messages import Status, StartStop, StartStopCmd, StartStopReply
from vif.data_interface.connection_manager import Key

from system.autostart.config import AutoStartConfig


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='Autostart')


class AutoStart(IOModule):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME

        # capture on start
        self._capture_on_start_thread: Optional[threading.Thread] = None
        self._config_apply_count = 0

        self._thread_handling_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._thread_stop_event = threading.Event()

        self.data_broker.capabilities.capture_data = False
        self.data_broker.capabilities.live_data = False

    def stop(self):
        self._stop_thread()
        self.logger.info('module closed')

    def _next_restart_time(self):
        cfg = self.config_handler.config

        # parse config values
        start_h = int(cfg['capture_restart_time'].split(":")[0])
        start_m = int(cfg['capture_restart_time'].split(":")[1])
        start_s = int(cfg['capture_restart_time'].split(":")[2])
        d = True if cfg['capture_restart_interval'] == 'Day' else False
        h = True if cfg['capture_restart_interval'] == 'Hour' else False
        m = True if cfg['capture_restart_interval'] == 'Minute' else False

        # get current date
        t = datetime.today()

        # compute future time to restart
        future = datetime(t.year, t.month, t.day, start_h if d else t.hour, start_m if h or d else t.minute, start_s)

        # advance to next restart time
        if future < t:
            future += timedelta(days=1 if d else 0, hours=1 if h else 0, minutes=1 if m else 0)

        return future

    def _capture_on_start_thread_fn(self):
        delay = self.config_handler.config['capture_on_start_delay_s']
        self.logger.debug("Capture on Start: Starting in " + str(delay) + " seconds.")

        # wait for delay seconds
        self._thread_stop_event.wait(delay)
        # make sure event was not set
        if self._thread_stop_event.is_set():
            self.logger.debug("Capture on start aborted, thread event is set.")
            return

        while not self._thread_stop_event.is_set():
            # optionally start sampling before capturing, so that a restart does not stop devices
            if self.config_handler.config['sampling_before_capture_on_start']:
                self.logger.info("Capture on start: sending start sampling command!")
                message = StartStop(cmd=StartStopCmd.START)
                reply = self.module_interface.cm.request(Key(self.module_interface.db_id, 'c', 'cmd_sampling'),
                                                         data=message.serialize(), timeout=5)
                # make sure there is a reply
                if reply is None:
                    self.logger.error("Capture on start: No start-sampling-reply received, trying again in 1 second.")
                    self._thread_stop_event.wait(1)
                    continue
                # wait a little before starting capture
                self._thread_stop_event.wait(1)

            # send start capture message
            self.logger.info("Capture on start: sending start capture command!")
            message = StartStop(cmd=StartStopCmd.START)
            reply = self.module_interface.cm.request(Key(self.module_interface.db_id, 'c', 'cmd_capture'),
                                                     data=message.serialize(), timeout=5)

            # make sure there is a reply
            if reply is None:
                self.logger.error("Capture on start: No reply received, trying again in 1 second.")
                self._thread_stop_event.wait(1)
                continue

            # parse reply
            start_reply = StartStopReply.deserialize(reply)

            # check the reply status
            if start_reply.status.error:
                self.logger.error("Capture on start: Done, capture is already running.")
            else:
                self.logger.debug("Capture on start: Done!")

            break

    def _worker_thread_fn(self):
        self.logger.debug('worker thread running')
        future = self._next_restart_time()
        self.logger.debug("Next Restart in: " + str(future - datetime.today()) + " at time: " + str(future))

        while not self._thread_stop_event.is_set():
            try:
                t = datetime.today()

                # sleep
                if future > t:
                    diff = (future - t).total_seconds()
                    diff = max(diff / 2, 0.1)
                    self._thread_stop_event.wait(diff)
                    continue

                if self.module_interface.capturing_active():
                    self.logger.info("Restarting capture: sending restart capture command!")
                    message = StartStop(cmd=StartStopCmd.RESTART)
                    reply = self.module_interface.cm.request(Key(self.module_interface.db_id, 'c', 'cmd_capture'),
                                                             data=message.serialize(), timeout=7)
                    restart_reply = StartStopReply.deserialize(reply)

                    if restart_reply.status.error:
                        self.logger.error("Capture restart returned with error.")
                        self.module_interface.log_gui("Capture restart returned with error.")
                        continue

                future = self._next_restart_time()
                self.logger.debug("Next Restart in: " + str(future - datetime.today()) + " at time: " + str(future))

            except Exception as e:
                self.logger.error(f'Exception in worker: {type(e).__name__}: {e}\n{traceback.format_exc()}')

        self.logger.debug('thread gone')

    def _start_thread(self, locking=True):
        if locking:
            self._thread_handling_lock.acquire()

        if self._worker_thread and self._worker_thread.is_alive():
            self.logger.warning('_start_thread: thread already running')
        else:
            self._thread_stop_event.clear()
            self._worker_thread = threading.Thread(target=self._worker_thread_fn, name='worker')
            self._worker_thread.start()

        if locking:
            self._thread_handling_lock.release()

    def _stop_thread(self, locking=True):
        if locking:
            self._thread_handling_lock.acquire()

        if self._worker_thread:
            self._thread_stop_event.set()
            self._worker_thread.join()
            self._worker_thread = None

        if self._capture_on_start_thread:
            self._thread_stop_event.set()
            self._capture_on_start_thread.join()
            self._capture_on_start_thread = None

        if locking:
            self._thread_handling_lock.release()

    def command_validate_config(self, config) -> Status:
        time_str = config['capture_restart_time']
        s = time_str.split(":")
        if len(s) != 3 or not s[0].isnumeric() or not s[1].isnumeric() or not s[2].isnumeric() \
                or len(s[0]) != 2 or len(s[1]) != 2 or len(s[2]) != 2 or \
                int(s[0]) < 0 or int(s[0]) > 23 or int(s[1]) < 0 or int(s[1]) > 59 or int(s[2]) < 0 or int(s[2]) > 59:
            return Status(error=True, title="Capture Restart Time",
                          message="Time must be in format hh:mm:ss, where 0 < hh < 24, 0 < mm < 60 and 0 < ss < 60.")

        if config['capture_on_start_delay_s'] < 0:
            return Status(error=True, title="Capture on Start", message="Capture on start delay must be > 0")

        return Status(error=False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        self._config_apply_count += 1

        try:
            # make sure thread re-spawn is not intercepted
            with self._thread_handling_lock:
                self._stop_thread(locking=False)

                if config['capture_on_start_enabled'] and self._config_apply_count == 1:
                    self._capture_on_start_thread = threading.Thread(target=self._capture_on_start_thread_fn,
                                                                     name='capture_on_start_thread')
                    self._capture_on_start_thread.start()

                if config['capture_restart_enabled']:
                    self._start_thread(locking=False)
            return Status(error=False)

        except Exception as e:
            self.logger.error(f'error applying config: {type(e).__name__}: {e}\n{traceback.format_exc()}')
            return Status(error=True, title=type(e).__name__, message=str(e))

    def command_prepare_sampling(self):
        self.logger.info('prepare sampling!')
        if self.config_handler.config['capture_restart_enabled']:
            self._start_thread(locking=False)


if __name__ == '__main__':
    main(AutoStart, AutoStartConfig, environ.to_config(ModuleEnv).MODULE_NAME)
