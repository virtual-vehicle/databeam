import multiprocessing
import multiprocessing.synchronize
from dataclasses import dataclass
from pathlib import Path
import re
from functools import lru_cache
from typing import Optional, Dict, Tuple, List

from vif.logger.logger import LoggerMixin
from vif.data_interface.network_messages import ModuleDataConfig
from vif.data_interface.data_capture_worker import DataCaptureWorker
from vif.data_interface.data_live_forwarder import DataLiveForwarder


@dataclass
class Capabilities:
    capture_data: bool
    live_data: bool


class DataBroker(LoggerMixin):
    def __init__(self, *args, db_id: str, db_router: str, data_dir: Path, module_name: str, module_type: str,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.data_dir = data_dir
        self.module_name = module_name
        self.module_type = module_type
        self.capabilities: Capabilities = Capabilities(capture_data=True, live_data=True)

        # replace the following characters in channel names for mcap compatibility
        self._replace_name_chars_re = re.compile(r'[^a-zA-Z0-9_-]')
        self._latest_data: Optional[Tuple[int, Dict]] = None

        self._possible_schema_change_event = multiprocessing.Event()

        self._child_shutdown_ev = multiprocessing.Event()

        self.data_capture_worker = DataCaptureWorker(module_name=module_name, module_type=module_type,
                                                     child_shutdown_ev=self._child_shutdown_ev,
                                                     data_dir=self.data_dir)

        self.data_live_forwarder = DataLiveForwarder(module_name=module_name, db_id=db_id,
                                                     db_router=db_router, child_shutdown_ev=self._child_shutdown_ev,
                                                     schema_change_ev=self._possible_schema_change_event)

    def start_capture_process(self):
        if self.capabilities.capture_data:
            self.data_capture_worker.start_process()

    def start_live_process(self):
        if self.capabilities.live_data:
            self.data_live_forwarder.start_process()

    def configure_live(self, data_config: ModuleDataConfig):
        if self.capabilities.live_data:
            self.data_live_forwarder.configure_live(data_config)

    def get_module_data_dir(self, measurement_name: str) -> Path:
        return self.data_capture_worker.get_module_data_dir(measurement_name)

    def prepare_capturing(self, measurement_name: str, data_schemas: List[Dict]):
        if self.capabilities.capture_data:
            self.data_capture_worker.prepare_capturing(measurement_name, data_schemas)

    def start_capturing(self) -> bool:
        """
        returns True on error
        """
        if self.capabilities.capture_data:
            return self.data_capture_worker.start_capturing()
        return False

    def stop_capturing(self):
        if self.capabilities.capture_data:
            self.data_capture_worker.stop_capturing()

    def notify_possible_schema_change(self):
        self.logger.debug('possible schema change detected')
        self._possible_schema_change_event.set()

    @lru_cache(maxsize=1024)
    def replace_name_chars(self, name):
        return self._replace_name_chars_re.sub('_', name)

    def data_in(self, time_ns: int, data: Dict, schema_index: int = 0,
                mcap: bool = True, live: bool = True, latest: bool = True):
        # check channel names and replace
        # TODO timeit @lru_cache and use replace function
        data = {self.replace_name_chars(key): value for key, value in data.items()}

        # store data as latest data if flag is set
        if latest:
            self._latest_data = (time_ns, data)

        # pass data to worker processes for mcap-writing
        if self.data_capture_worker.is_active() and mcap:
            self.data_capture_worker.capture_data(time_ns, schema_index, data)

        # forward live-data only if needed
        if self.data_live_forwarder.is_active() and live:
            self.data_live_forwarder.forward_data(time_ns, schema_index, data)

    def get_latest(self) -> Tuple[int, Optional[Dict]]:
        if self._latest_data is None:
            return 0, None

        return self._latest_data[0], self._latest_data[1].copy()

    def close(self):
        # stop capturing / live data inputs
        self.data_capture_worker.toggle_active(False)
        self.data_live_forwarder.toggle_active(False)

        # stop child processes
        self._child_shutdown_ev.set()

        self.data_capture_worker.close()
        self.data_live_forwarder.close()

        self.logger.info('close succeeded')
