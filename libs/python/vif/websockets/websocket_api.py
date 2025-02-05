import threading
import json
import logging
from typing import Optional, List

import websockets.exceptions
import websockets.sync.server as ws_server

from vif.logger.logger import LoggerMixin


class WSClient:
    def __init__(self, uuid: int, websocket: ws_server.ServerConnection):
        self.client_id: int = uuid
        self.websocket: ws_server.ServerConnection = websocket


class WebSocketAPI(LoggerMixin):
    def __init__(self, *args, ip: str, port: int, **kwargs):
        super().__init__(*args, **kwargs)
        self._ip = ip
        self._port = port
        self._server: Optional[ws_server.WebSocketServer] = None
        self._server_thread: Optional[threading.Thread] = None

        self._client_id_counter: int = 0

        self._clients: List[WSClient] = []
        self._clients_lock = threading.Lock()

        # suppress websocket library logging
        logging.getLogger("websockets").setLevel(logging.WARNING)

    def start_server(self):
        self._server_thread = threading.Thread(target=self._server_run, name='ws_server_thread')
        self._server_thread.start()

    def shutdown(self):
        with self._clients_lock:
            for c in self._clients:
                c.websocket.close()
        if self._server is not None:
            self._server.shutdown()
        self.logger.info("joining server thread")
        if self._server_thread is not None:
            self._server_thread.join()
        self.logger.info("Server Closed.")

    def get_client_ids(self) -> List[int]:
        with self._clients_lock:
            ids = [x.client_id for x in self._clients]
            return ids

    def _server_run(self):
        self.logger.info("Create WebSocket Server: " + self._ip + ":" + str(self._port))
        self._server = ws_server.serve(self._ws_handler, self._ip, self._port)
        self._server.serve_forever()
        self.logger.info("WebSocket server closed.")

    def broadcast_json_str(self, msg_type, json_str, client_ids: Optional[List[int]] = None):
        msg = {'type': msg_type, 'data': json_str}
        with self._clients_lock:
            for c in self._clients:
                if client_ids is None or c.client_id in client_ids:
                    try:
                        c.websocket.send(json.dumps(msg))
                    except Exception as e:
                        self.logger.error(f"broadcast_json_str EX client {c.client_id}: {type(e).__name__}: {e}")

    def _ws_handler(self, websocket: ws_server.ServerConnection):
        # add new client
        with self._clients_lock:
            self._client_id_counter += 1
            self._clients.append(WSClient(self._client_id_counter, websocket))
            try:
                websocket.send(json.dumps({'type': 'id', 'id': self._client_id_counter}))
            except Exception as e:
                self.logger.error(f"_ws_handler EX client {self._client_id_counter} send id failed: "
                                  f"{type(e).__name__}: {e}")
            else:
                self.logger.info("Client %d connected (total: %d)",
                                 self._client_id_counter, len(self._clients))

        # wait
        try:
            while True:
                received = websocket.recv()
                self.logger.info("Received: %s", received)
        except websockets.exceptions.ConnectionClosed:
            pass

        # remove client
        with self._clients_lock:
            self._clients = [x for x in self._clients if x.websocket is not websocket]
            self.logger.info("Client disconnected. (total: %d)", len(self._clients))
