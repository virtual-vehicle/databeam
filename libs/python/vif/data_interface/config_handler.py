import json
import os
import re
import shutil
import threading
from datetime import datetime
from typing import Type, Dict, Any, List, Optional
from pathlib import Path
from copy import deepcopy

from vif.logger.logger import LoggerMixin
from vif.data_interface.base_config import BaseConfig

NR_BACKUP_CONFIGS = 100

class ConfigHandler(LoggerMixin):
    def __init__(self, *args, config_type: Type[BaseConfig], **kwargs):
        super().__init__(*args, **kwargs)
        self.lock = threading.Lock()
        self._config_type = config_type
        self.type = config_type.Name
        self._config_dir = Path('.')
        self._config: Dict[str, Any] = {}
        self._add_missing_keys_enabled = True
        self._config_filename = "config.json"

    def disable_add_missing_keys(self):
        self._add_missing_keys_enabled = False

    def _add_missing_keys(self, config: Dict) -> Dict:
        if not self._add_missing_keys_enabled:
            return config

        defaults = self.get_default_config()
        for k, v in defaults.items():
            if k not in config:
                config[k] = v
        # maintain order of keys in defaults
        return {k: config[k] for k in defaults.keys()}

    @property
    def config(self) -> Dict:
        with self.lock:
            config = deepcopy(self._config)
        return self._add_missing_keys(config)

    @config.setter
    def config(self, value: Dict[str, Any]) -> None:
        with self.lock:
            self._config.update(value)
            self._config = self._add_missing_keys(self._config)

    def config_json(self) -> str:
        with self.lock:
            return json.dumps(self._add_missing_keys(self._config))

    def set_config_dir(self, cfg_dir: Path):
        self._config_dir = cfg_dir
        # load existing or default _config
        self._config = self.read_config()

    def write_config(self, config: Optional[Dict] = None):
        with self.lock:
            if config is not None:
                self._config = self._add_missing_keys(deepcopy(config))

            write_config = not self._check_config_path(repair=True) or self._config != self._read_config_file()

            # only write if config has changed
            if write_config:
                self._config_type.json_to_disk(self._config_dir, self._config_filename, self._config)
                self.backup_timestamped_config(files_to_keep=NR_BACKUP_CONFIGS)

    def backup_timestamped_config(self, files_to_keep: int):
        """
        Backups the last n config files by renaming them with a given timestamp.
        """
        config_time_format = "%Y%m%d_%H%M%S"

        def remove_invalid_files(filename_list: List) -> List:
            """
            Removes files from list that don't have a timestamp as extension.
            """
            filename_list_keep = []
            for curr_file in filename_list:
                if re.match(r'^config\.[0-9]{8}_[0-9]{6}\.json$', curr_file):
                    filename_list_keep.append(curr_file)
            return filename_list_keep

        def remove_old_configs(sorted_filename_list):
            """
            Takes the first timestamped file of the sorted list and removes it. Always removes the oldest files
            in a pre-sorted list.
            """
            config_file_count = len(sorted_filename_list)
            for curr_file in sorted_filename_list:
                if config_file_count <= files_to_keep:
                    break
                os.remove(str(self._config_dir) + os.sep + curr_file)
                config_file_count -= 1

        # copy current config file as timestamped backup
        file_timestamp = datetime.now().strftime(config_time_format)
        new_file = f"config.{file_timestamp}.json"
        try:
            shutil.copy2(str(self._config_dir) + os.sep + "config.json", str(self._config_dir) + os.sep + new_file)
        except FileNotFoundError:
            pass
        else:
            # cleanup: only keep last n backups
            filenames = os.listdir(self._config_dir)
            filenames = remove_invalid_files(filenames)
            remove_old_configs(sorted(filenames))

    def _read_config_file(self) -> Dict:
        return self._config_type.json_from_disk(self._config_dir, self._config_filename,
                                                self._config_type.get_default_config())

    def _check_config_path(self, repair: bool) -> bool:
        """
        Checks if the directory and the file of the config exist.
        :param repair: If True, it creates the directory if it does not exist.
        :return: True if directory and file exist.
        """
        if not os.path.isdir(self._config_dir):
            if repair:
                os.mkdir(self._config_dir)
                return False
        if not os.path.isfile(str(self._config_dir) + os.sep + self._config_filename):
            return False
        return True

    def read_config(self) -> Dict:
        with self.lock:
            return self._add_missing_keys(self._read_config_file())

    def get_default_config(self) -> Dict:
        return self._config_type.get_default_config()

    def get_default_json(self) -> str:
        return json.dumps(self.get_default_config())

    def valid(self, config: Optional[Dict] = None):
        if config is None:
            with self.lock:
                return self._config_type.validate_config(self._config)
        else:
            return self._config_type.validate_config(config)
