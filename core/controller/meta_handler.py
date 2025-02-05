"""
Stores the meta data of the system and contains methods to edit it.
Differentiates between
    - system meta data  (changed upon command and start/stop measurement)
    - dynamic meta data (changed upon start/stop measurement)
    - user meta data    (changed upon command)
"""

import traceback
from pathlib import Path
import json
import threading
from typing import Dict, Union

from vif.logger.logger import LoggerMixin


class MetaHandler(LoggerMixin):
    filename_system_meta = 'system_meta.json'
    filename_user_meta = 'user_meta.json'

    def __init__(self, *args, config_dir: Path, hostname: str, db_id: str, deploy_version: str, **kwargs):
        super().__init__(*args, **kwargs)
        self._config_dir = config_dir

        # lock access to meta files
        self._system_meta_lock = threading.Lock()
        self._user_meta_lock = threading.Lock()
        self._dynamic_meta_lock = threading.Lock()

        self._system_meta_data: Dict[str, Union[str, int, Dict]] = {
            'hostname': hostname,
            'DB_ID': db_id,
            'DEPLOY_VERSION': deploy_version,
            'run_id': 1,
            'run_tag': 'unset',
        }
        self._dynamic_meta_data: Dict[str, Union[str, int, Dict]] = {
            'start_time_utc': '',  # e.g. '2020-01-31T13:46:17.869750' from datetime.now(timezone.utc).isoformat()
            'stop_time_utc': '',
            'duration': ''  # e.g. '2 days, 0:00:01.123'
        }
        self._user_meta_data: Dict[str, Union[str, int, Dict]] = {}

        # load system meta-data from disk
        with self._system_meta_lock:
            file_path = self._config_dir / self.filename_system_meta
            try:
                with file_path.open('r') as f:
                    self._system_meta_data.update(json.load(f))
                    self.logger.debug(f'Read system-meta JSON {file_path} from disk: {self._system_meta_data}')
                    # update with launch-specific data
                    self._system_meta_data.update(
                        {'hostname': hostname, 'DB_ID': db_id, 'DEPLOY_VERSION': deploy_version})
            except FileNotFoundError:
                self.logger.debug('No system-meta available, writing default')
                with file_path.open('w') as f:
                    json.dump(self._system_meta_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                self.logger.error(f'Reading system-meta failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')
        # load user meta-data from disk
        with self._user_meta_lock:
            try:
                file_path = self._config_dir / self.filename_user_meta
                with file_path.open('r') as f:
                    self._user_meta_data.update(json.load(f))
                    self.logger.debug(f'Read user-meta JSON {file_path} from disk: {self._user_meta_data}')
            except FileNotFoundError:
                self.logger.debug('No user-meta available')
            except Exception as e:
                self.logger.error(f'Reading user-meta failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')

    def get_combined_meta(self) -> Dict[str, Union[str, int, Dict]]:
        meta_data: Dict[str, Union[str, int, Dict]] = self.get_system_meta()
        meta_data['user_meta'] = self.get_user_meta()
        meta_data.update(self.get_dynamic_meta())
        return meta_data

    def get_system_meta(self) -> Dict[str, Union[str, int, Dict]]:
        with self._system_meta_lock:
            return self._system_meta_data.copy()

    def update_system_meta(self, meta_data: Dict):
        with self._system_meta_lock:
            # make sure run_id is an integer
            if 'run_id' in meta_data:
                meta_data['run_id'] = int(meta_data['run_id'])
            self._system_meta_data.update(meta_data)
            # save system_meta
            try:
                file_path = self._config_dir / self.filename_system_meta
                with file_path.open('w') as f:
                    self.logger.debug(f'Saving system-meta JSON {file_path} to disk: {self._system_meta_data}')
                    json.dump(self._system_meta_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                self.logger.error(f'save_system_meta failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')

    def get_user_meta(self) -> Dict[str, Union[str, int, Dict]]:
        with self._user_meta_lock:
            return self._user_meta_data.copy()

    def update_user_meta(self, meta_data: Dict):
        with self._user_meta_lock:
            try:
                self._user_meta_data = meta_data.copy()

                file_path = self._config_dir / self.filename_user_meta
                with file_path.open('w') as f:
                    self.logger.debug(f'Update user-meta JSON {file_path} to disk: {self._user_meta_data}')
                    json.dump(self._user_meta_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                self.logger.error(f'update_user_meta failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')

    def get_dynamic_meta(self) -> Dict[str, Union[str, int, Dict]]:
        with self._dynamic_meta_lock:
            return self._dynamic_meta_data.copy()

    def update_dynamic_meta(self, meta_data: Dict):
        with self._dynamic_meta_lock:
            self._dynamic_meta_data.update(meta_data)
