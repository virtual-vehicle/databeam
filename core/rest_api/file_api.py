"""
Allows the Rest API to download and delete measurement data and log files.
"""

import json
from pathlib import Path
import os
import datetime as dt
import shutil
from typing import List

from vif.logger.logger import LoggerMixin


class FileAPI(LoggerMixin):
    def __init__(self, *args, data_dir, logs_dir, **kwargs):
        super().__init__(*args, **kwargs)

        # make sure a data_dir is provided
        assert len(str(data_dir)) > 1
        self._data_dir = data_dir

        # make sure a logs_dir is provided
        assert len(str(logs_dir)) > 1
        self._logs_dir = logs_dir

    def get_measurements(self):
        dirs_files = self._walk_directory(self._data_dir)
        dirs = dirs_files['directories']
        measurement_names = [x for x in dirs if len(x.split("/")) == 1]

        measurements = []

        for m in measurement_names:
            # path to measurement meta file
            meta_path = str(self._data_dir) + "/" + m + "/meta.json"

            # holds all measurement info
            measurement_dict = {}

            # add measurement meta to info
            try:
                measurement_dict['meta'] = {}
                with open(meta_path) as f:
                    measurement_dict['meta'] = json.load(f)
            except FileNotFoundError:
                self.logger.warning(f"Meta file not found: {meta_path}")
            except Exception as e:
                self.logger.error(f"Meta file read error ({type(e).__name__}): {e}")

            # holds total size in bytes for measurement
            total_size_bytes = 0

            # count total size
            for x in dirs_files['files']:
                if x[0].startswith(m):
                    total_size_bytes += x[1]

            # store measurement info
            measurement_dict['measurement'] = m
            measurement_dict['total_size_bytes'] = total_size_bytes
            measurement_dict['modules'] = self.get_modules(m, dirs)
            measurements.append(measurement_dict)

        # sort measurements by name (timestamp)
        measurements.sort(key=lambda _m: _m['measurement'])

        return measurements

    def remove_measurement(self, measurement_name):
        if len(measurement_name) == 0:
            return False

        dir_path = str(self._data_dir) + "/" + measurement_name

        if os.path.exists(dir_path):
            self.logger.info("Removing measurement dir: " + dir_path)
            shutil.rmtree(dir_path)
            return True

        return False

    def get_modules(self, measurement, dirs=None):
        if dirs is None:
            dirs = self._walk_directory(self._data_dir)['directories']

        modules = []

        for x in dirs:
            p = x.split("/")
            if len(p) == 2 and p[0] == measurement:
                modules.append(p[1])

        return modules

    def get_measurement_files(self, measurements: List[str]):
        files = self.get_files()
        l = []

        for x in files:
            for m in measurements:
                if x[0].startswith(m):
                    l.append(x[0])
                    break

        return l

    def get_log_files(self):
        file_infos = self._walk_directory(self._logs_dir)['files']
        files = []

        for f in file_infos:
            files.append(f[0])

        return files

    def get_files(self):
        return self._walk_directory(self._data_dir)['files']

    def _walk_directory(self, path, ignore_directory_list: List = None):
        if ignore_directory_list is None:
            ignore_directory_list = []

        content = {"directories": [], "files": []}

        # walk through all files and directories
        for root, directories, files in os.walk(path, topdown=True):
            # remove ignore directories from list in-place! Only works with topdown=True
            directories[:] = [x for x in directories if x not in ignore_directory_list]

            # create relative path
            rel_dir = os.path.relpath(root, path)

            # iterate files
            for name in files:
                file_name = str(os.path.join(rel_dir, name))
                file_size = os.path.getsize(os.path.join(root, name))
                file_time = dt.datetime.fromtimestamp(
                    os.path.getctime(os.path.join(root, name)), dt.timezone(dt.timedelta(hours=1)))
                if file_name.startswith('./'):
                    file_name = file_name[2:]
                content["files"].append([file_name, file_size, file_time.strftime("%d.%m.%Y, %H:%M")])

            # iterate directories
            for name in directories:
                file_name = str(os.path.join(rel_dir, name))

                if file_name.startswith('./'):
                    file_name = file_name[2:]

                content["directories"].append(file_name)

        return content
    