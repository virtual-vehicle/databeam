"""
Allows the Rest API to request preview measurement data for every module.
"""

import threading
from typing import Optional, Dict, List, Tuple
from collections import defaultdict

from vif.websockets.websocket_api import WebSocketAPI
from vif.logger.logger import LoggerMixin

from controller_api import ControllerAPI


class PreviewAPI(LoggerMixin):
    def __init__(self, *args, controller_api: ControllerAPI, websocket_api: WebSocketAPI, **kwargs):
        super().__init__(*args, **kwargs)
        self._controller_api = controller_api
        self._websocket_api = websocket_api
        self._request_dict: Dict[int, Tuple[str, int]] = {}

        self._preview_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        self._request_lock = threading.Lock()

    def start(self):
        self._preview_thread = threading.Thread(target=self._run, name='ws_server_thread')
        self._preview_thread.start()
        self.logger.info("Running.")

    def shutdown(self):
        self._shutdown_event.set()
        if self._preview_thread is not None:
            self._preview_thread.join()
        self.logger.info("Shutdown.")

    def request_data(self, client_id: int, module_name: str, schema_index: int = 0):
        self.logger.info('Client %d requests live data for module "%s"', client_id, module_name)
        with self._request_lock:
            self._request_dict[client_id] = (module_name, schema_index)

    def _run(self):
        while not self._shutdown_event.is_set():
            clients = self._websocket_api.get_client_ids()

            modules_dict: Dict[str, List[Tuple[int, int]]] = defaultdict(list)

            with self._request_lock:
                # remove requests from disconnected clients
                self._request_dict = {k: v for k, v in self._request_dict.items() if k in clients}

                # create dict module -> list of clients
                for client_id, (module_name, schema_index) in self._request_dict.items():
                    modules_dict[module_name].append((client_id, schema_index))

            # self.logger.debug("Fetch Preview: %s", modules_dict)

            for module, client_schema_list in modules_dict.items():
                client_list = [x[0] for x in client_schema_list]
                schema_index = client_schema_list[0][1]
                latest_json_str = self._controller_api.get_module_latest(module, schema_index=schema_index)
                self._websocket_api.broadcast_json_str(msg_type="preview", json_str=latest_json_str,
                                                       client_ids=client_list)
                # self.logger.debug("LATEST %s: %s", module, latest_json_str)

            self._shutdown_event.wait(1.0)
