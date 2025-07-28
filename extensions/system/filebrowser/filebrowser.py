"""
Template for IO-Module
Please consult libs/python/vif/data_interface/io_module.py for callback / base-class documentation
"""
import threading
import traceback
from typing import Optional, Dict, Union, List
import time
import os
import signal
import subprocess

import environ

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.data_interface.module_meta_factory import ModuleMetaFactory
from vif.asyncio_helpers.asyncio_helpers import tick_generator
from vif.data_interface.network_messages import Status, IOEvent
from vif.jobs.job_entry import EventJob

from system.filebrowser.config import FileBrowserConfig  # TODO adopt import path and name


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='FileBrowser')  # TODO adopt module name
    # TODO define any needed environment variables here


class FileBrowser(IOModule):  # TODO adopt module name
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME

        self.port: int = 8044
        self.username: str = "admin"
        self.password: str = "admin"
        self.allow_delete: bool = False
        self.filebrowser_proc: Optional[subprocess.Popen] = None

        self.data_broker.capabilities.capture_data = False
        self.data_broker.capabilities.live_data = False


    @staticmethod
    def get_filebrowser_location():
        """
        Required to make it work in docker and outside, since the working directories are differently set.
        """
        cwd = os.getcwd()
        if cwd.split("/")[-1] == "filebrowser":
            return "/"
        else:
            return "/io_modules/filebrowser/"

    def init_filebrowser(self):
        """
        Initializes the filebrowser configuration.
        """
        self.logger.info("Initalizing filebrowser config.")
        config_proc: subprocess.Popen = subprocess.Popen([f".{self.get_filebrowser_location()}filebrowser/filebrowser",
                                                          "config", "init"],
                                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        config_proc.wait(2)

        user_proc :subprocess.Popen = subprocess.Popen([f".{self.get_filebrowser_location()}filebrowser/filebrowser",
                                                        "users", "add",
                                                        self.username, self.password],
                                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        user_proc.wait(2)


    def deelevate_user(self):
        """
        Used to de-elevate the permissions of the first user from admin into regular mode. We do not need an admin,
        since we create filebrowser fresh on every new start of the system.
        We also remove the users permission to delete and create files and directories for data safety reasons.
        """
        self.logger.info("Deelevating admin user.")

        user_proc: subprocess.Popen = subprocess.Popen([f".{self.get_filebrowser_location()}filebrowser/filebrowser",
                                                             "users", "update", self.username,
                                                             "--perm.admin=false",
                                                             f"--perm.create=false",
                                                             f"--perm.delete={str(self.allow_delete).lower()}"],
                                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        user_proc.wait(2)

    def start_filebrowser(self):
        """
        Starts the filebrowser process.
        """
        self.logger.info("Starting filebrowser.")
        self.filebrowser_proc = subprocess.Popen([f".{self.get_filebrowser_location()}filebrowser/filebrowser",
                                                  #"-c", f".{self.get_filebrowser_location()}filebrowser/config.yml"
                                                  "-r", str(self.module_interface.data_broker.data_dir),
                                                  "--address", "0.0.0.0",
                                                  "--port", f"{self.port}"],
                                                 preexec_fn=os.setsid,
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def config_filebrowser(self):
        """
        Configures the filebrowser software for custom use.
        """
        self.logger.info("Configuring filebrowser branding.")
        config_proc: subprocess.Popen = subprocess.Popen([f".{self.get_filebrowser_location()}filebrowser/filebrowser",
                                                          "config", "set",
                                                          "--branding.files", f".{self.get_filebrowser_location()}branding",
                                                          "--branding.name", "DataBeam Filebrowser",
                                                          "--branding.disableExternal"],
                                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        config_proc.wait(2)

    def update_user(self, old_username: str, new_username: str, new_password: str):
        """
        Used to update the first user. Changes its name and password.
        :param old_username: The old username to change.
        :param new_username: The new username to change to.
        :param new_password: The password of the first user.
        """
        self.logger.info("Updating user information.")
        user_proc: subprocess.Popen = subprocess.Popen([f".{self.get_filebrowser_location()}filebrowser/filebrowser",
                                                        "users", "update", f"{old_username}",
                                                        "--username", f"{new_username}",
                                                        "--password", f"{new_password}"],
                                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        user_proc.wait(2)

    def stop_filebrowser(self):
        """
        Stops the currently active stacking daemon when one exists. The daemon will continue to work until finished.
        It will then be collected by the daemon collector thread. This method is called when a measurement is stopped
        to ensure the stacking of all left video files in the data directory.
        """
        if self.filebrowser_proc is None:
            return
        self.logger.info("Stopping filebrowser.")
        os.killpg(os.getpgid(self.filebrowser_proc.pid), signal.SIGINT)
        self.filebrowser_proc.wait(2)
        self.filebrowser_proc = None

    def start(self):
        self.logger.debug('starting')
        self.init_filebrowser()

    def command_validate_config(self, config: Dict) -> Status:
        if config["username"] == "" or config["password"] == "":
            return Status(error=True, message="Please set a username and password.")
        return Status(error=False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            self.stop_filebrowser()
            old_username: str = self.username
            self.port = config["port"]
            self.username = config["username"]
            self.password = config["password"]
            self.allow_delete = config["allow_delete_data"]
            self.config_filebrowser()
            self.update_user(old_username, self.username, self.password)
            self.deelevate_user()
            self.start_filebrowser()

            event_job = EventJob(self.module_interface.cm, self.module_interface.db_id)
            event_job.set_modules_changed(True).set_done().update()

            return Status(error=False)

        except Exception as e:
            self.logger.error(f'error applying config: {type(e).__name__}: {e}\n{traceback.format_exc()}')
            return Status(error=True, title=type(e).__name__, message=str(e))

    def command_config_event(self, cfg_key: str) -> None:
        self.logger.debug('Received event_data: %s', cfg_key)

        if cfg_key == 'my_button':
            self.logger.info('Button was pressed!')
        else:
            self.logger.warning('Received unknown config event.')

    def command_get_meta_data(self) -> ModuleMetaFactory:
        meta = ModuleMetaFactory()
        meta.add_webinterface(f"FileBrowser", f"{self.port}")
        return meta


if __name__ == '__main__':
    main(FileBrowser, FileBrowserConfig, environ.to_config(ModuleEnv).MODULE_NAME)  # TODO adopt module name and config class
