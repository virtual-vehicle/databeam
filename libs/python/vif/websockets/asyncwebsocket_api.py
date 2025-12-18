import threading
import json
import logging
from typing import Optional, List
import asyncio
import websockets
from websockets.server import WebSocketServerProtocol

from vif.logger.logger import LoggerMixin


class WSClient:
    def __init__(self, uuid: int, websocket: WebSocketServerProtocol, loop: asyncio.AbstractEventLoop,
                 max_queue_size: int = 10):
        self.client_id: int = uuid
        self.websocket: WebSocketServerProtocol = websocket
        self.loop = loop
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.max_queue_size = max_queue_size

        # start sender task
        self.sender_task = asyncio.run_coroutine_threadsafe(self._send_loop(), loop)

    async def _send_loop(self):
        try:
            while True:
                msg = await self.queue.get()

                if msg is None:
                    break

                await self.websocket.send(msg)
        except websockets.exceptions.ConnectionClosed:
            pass

    def enqueue_message(self, msg: str):
        async def _enqueue():
            if self.queue.full():
                try:
                    dropped_msg = self.queue.get_nowait()  # drop oldest
                    #print("drop: " + dropped_msg[:20])
                except asyncio.QueueEmpty:
                    pass
            await self.queue.put(msg)

        asyncio.run_coroutine_threadsafe(_enqueue(), self.loop)

    async def close(self):
        await self.queue.put(None)
        await self.websocket.close()
        await asyncio.wrap_future(self.sender_task)


class AsyncWebSocketAPI(LoggerMixin):
    def __init__(self, *args, ip: str, port: int, **kwargs):
        super().__init__(*args, **kwargs)
        self._ip = ip
        self._port = port

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Optional[websockets.server.Serve] = None
        self._server_thread: Optional[threading.Thread] = None

        self._client_id_counter: int = 0
        self._clients: List[WSClient] = []
        self._clients_lock = threading.Lock()

        # suppress websocket library logging
        logging.getLogger("websockets").setLevel(logging.WARNING)

    def start_server(self):
        self._server_thread = threading.Thread(target=self._start_loop, name='ws_server_thread', daemon=True)
        self._server_thread.start()

    def _start_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_server())
        self._loop.run_forever()

    async def _run_server(self):
        self.logger.info(f"Create WebSocket Server: {self._ip}:{self._port}")
        self._server = await websockets.serve(self._ws_handler, self._ip, self._port)
        self.logger.info("WebSocket server running.")

    def shutdown(self):
        self.logger.info("Shutdown Async Websocket API")
        self._shutdown_sync()
        self.logger.info("Async Websocket API Closed.")

    async def _shutdown_async(self):
        # close all clients
        with self._clients_lock:
            close_tasks = [c.close() for c in self._clients]
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)

        # stop accepting new connections
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    def _shutdown_sync(self):
        if self._loop is not None:
            # schedule async shutdown
            future = asyncio.run_coroutine_threadsafe(self._shutdown_async(), self._loop)
            try:
                # wait for shutdown
                future.result(timeout=5)
            except Exception as e:
                self.logger.warning(f"Exception during shutdown: {e}")

            # stop the loop
            self._loop.call_soon_threadsafe(self._loop.stop)

        # join server thread
        if self._server_thread is not None:
            self._server_thread.join()

    def get_client_ids(self) -> List[int]:
        with self._clients_lock:
            return [c.client_id for c in self._clients]

    def broadcast_json_str(self, msg_type, json_str, client_ids: Optional[List[int]] = None):
        msg = json.dumps({'type': msg_type, 'data': json_str})
        with self._clients_lock:
            for c in self._clients:
                if client_ids is None or c.client_id in client_ids:
                    c.enqueue_message(msg)

    async def _ws_handler(self, websocket: WebSocketServerProtocol):
        # add new client
        with self._clients_lock:
            self._client_id_counter += 1
            client_id = self._client_id_counter
            client = WSClient(client_id, websocket, self._loop)
            self._clients.append(client)
            try:
                await websocket.send(json.dumps({'type': 'id', 'id': client_id}))
            except Exception as e:
                self.logger.error(f"_ws_handler EX client {client_id} send id failed: {type(e).__name__}: {e}")
            else:
                self.logger.info("Client %d connected (total: %d)", client_id, len(self._clients))

        try:
            async for message in websocket:
                self.logger.info("Received: %s", message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # remove client
            with self._clients_lock:
                filtered_clients = []

                for c in self._clients:
                    if c.websocket is websocket:
                        await c.close()
                    else:
                        filtered_clients.append(c)

                self._clients = filtered_clients

                #self._clients = [x for x in self._clients if x.websocket is not websocket]
                self.logger.info("Client disconnected. (total: %d)", len(self._clients))
