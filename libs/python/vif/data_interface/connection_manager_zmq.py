import logging
import queue
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
import random
from typing import Dict, Tuple, Callable, Optional, List
import os

import zmq
import environ

from vif.logger.logger import LoggerMixin
from vif.zmq.helpers import create_connect, flush_queue_sync


class ConnectionException(Exception):
    pass


@dataclass
class Key:
    db_id: str
    node_name: str
    topic: str

    @classmethod
    def from_ident_topic(cls, ident: str, topic: str):
        try:
            db_id, node_name = ident.split('/', 1)
        except ValueError:
            raise ValueError(f'Invalid identity: {ident}')
        return cls(db_id=db_id, node_name=node_name, topic=topic)

    def __post_init__(self):
        # remove slashes
        self.db_id = self.db_id.strip('/')
        self.node_name = self.node_name.strip('/')
        self.topic = self.topic.strip('/')

        assert len(self.db_id) > 0, 'db_id must not be empty'
        assert len(self.node_name) > 0, 'node_name must not be empty'
        assert len(self.topic) > 0, 'topic must not be empty'

        self._str = f'{self.db_id}/{self.node_name}/{self.topic}'
        self.ident = f'{self.db_id}/{self.node_name}'

    def __str__(self):
        return self._str

    def encode(self):
        return self._str.encode()


@dataclass
class QueryableEnvelope:
    ident: str  # target or return identity
    uuid: bytes
    topic: str
    payload: bytes

    @classmethod
    def from_multipart(cls, data):
        return cls(ident=data[0].decode(), uuid=data[1], topic=data[2].decode(), payload=data[3])

    def to_multipart(self):
        return [self.ident.encode(), self.uuid, self.topic.encode(), self.payload]

    def __str__(self):
        return f'[{self.ident}, {self.uuid.hex()}, {self.topic}, {self.payload.decode()}]'


@environ.config(prefix='')
class BrokerEnv:
    DB_ROUTER_FRONTEND_PORT = environ.var(help='DataBeam router queryable frontend port', default='5555')
    DB_ROUTER_BACKEND_PORT = environ.var(help='DataBeam router queryable backend port', default='5556')
    DB_ROUTER_SUB_PORT = environ.var(help='DataBeam router SUB port', default='5557')
    DB_ROUTER_PUB_PORT = environ.var(help='DataBeam router PUB port', default='5558')


class RouterConnection(LoggerMixin):
    def __init__(self, *args, db_id: str, router_hostname: str, node_name: str = '', **kwargs):
        """

        """
        super().__init__(*args, **kwargs)

        self.logger.info('initializing session with db_id "%s", node_name "%s", router "%s"',
                         db_id, node_name, router_hostname)

        self._db_id = db_id
        self._router_hostname = router_hostname
        self._node_name = node_name
        # ports for pub/sub, query front-/backend are assumed to be the same for all routers!
        self._ports = environ.to_config(BrokerEnv)
        self._shutdown_ev = threading.Event()

        # sockets
        self._pub_sock_lock = threading.Lock()
        self._pub_sock = create_connect(f'tcp://{self._router_hostname}:{self._ports.DB_ROUTER_SUB_PORT}', zmq,
                                        zmq.PUB)

        if len(self._node_name) > 0:
            ident_key = Key(self._db_id, self._node_name, topic='-')
            self._query_req_sock_lock = threading.Lock()
            self._query_req_sock = create_connect(f'tcp://{self._router_hostname}:'
                                                  f'{self._ports.DB_ROUTER_FRONTEND_PORT}',
                                                  zmq, zmq.DEALER, identity=ident_key.ident.encode(), timeout_ms=1000)
        else:
            self.logger.debug('node_name not specified: disabled queryables and queries')
            # external routers do not support queries
            self._query_req_sock_lock = None
            self._query_req_sock = None

        self._subscribers_lock = threading.Lock()
        # key (topic): list of uuids (int) and callbacks
        self._subscribers: Dict[str, List[Tuple[int, Callable[[str, bytes], None]]]] = {}
        # queue to task the worker thread to un-/subscribe to topics
        self._topic_transfer_q: queue.SimpleQueue[Tuple[bool, str]] = queue.SimpleQueue()

        self._queryables_lock = threading.Lock()
        # dict-key = topic --> callback
        self._queryables: Dict[str, Callable[[bytes], str | bytes]] = {}

        # worker threads
        self._subscribe_thread = threading.Thread(target=self._subscribe_worker, name='subscribe_worker')
        self._subscribe_thread.start()

        if len(self._node_name) > 0:
            self._queryable_thread = threading.Thread(target=self._queryable_worker, name='queryable_worker')
            self._queryable_thread.start()
        else:
            # external routers do not support queries
            self._queryable_thread = None

    def close(self):
        self.logger.info('closing connection to %s', self._db_id)
        self._shutdown_ev.set()
        if self._queryable_thread is not None:
            self._queryable_thread.join()
        self._subscribe_thread.join()
        with self._pub_sock_lock:
            self._pub_sock.close()
        if self._query_req_sock_lock is not None:
            with self._query_req_sock_lock:
                self._query_req_sock.close()

    def _queryable_worker(self) -> None:
        logger = logging.getLogger('_queryable_worker')
        ident_key = Key(db_id=self._db_id, node_name=self._node_name, topic='-')
        logger.debug('identity: %s', ident_key.ident)
        # TODO check if our ID is already registered by someone .. how?
        #  set uuid ident and ask + register a default-queryable here?

        sock = create_connect(f'tcp://{self._router_hostname}:{self._ports.DB_ROUTER_BACKEND_PORT}',
                              zmq, zmq.DEALER, identity=ident_key.ident.encode(), timeout_ms=100)
        sock.setsockopt(zmq.RCVHWM, 10000)
        sock.setsockopt(zmq.SNDHWM, 10000)

        while not self._shutdown_ev.is_set():
            try:
                msg = QueryableEnvelope.from_multipart(sock.recv_multipart())
                # logger.debug('rx from %s: %s', msg.ident, msg)
                key = Key.from_ident_topic(msg.ident, msg.topic)

                # find callback by key
                with self._queryables_lock:
                    cb = self._queryables.get(key.topic)
                if cb is None:
                    logger.warning(f'no callback registered for topic {key}')
                    continue
                new_payload = cb(msg.payload)

                if isinstance(new_payload, str):
                    msg.payload = new_payload.encode()
                elif new_payload is None:
                    msg.payload = b''
                else:
                    msg.payload = new_payload

                # return payload
                sock.send_multipart(msg.to_multipart())
            except zmq.Again:
                continue  # timeout: nothing received
            except Exception as e:
                logger.error(f'EX ({type(e).__name__}): {e}\n{traceback.format_exc()}')

        sock.close()

    def declare_queryable(self, key: Key, cb: Callable[[bytes], str | bytes]) -> str:
        self.logger.debug('registering queryable %s', key)
        assert str(key).startswith(f'{self._db_id}/{self._node_name}'), 'queryable key must start with node name'
        topic = key.topic
        with self._queryables_lock:
            assert topic not in self._queryables, f'queryable {topic} already registered'
            self._queryables[topic] = cb
        return topic

    def undeclare_queryable(self, topic: str) -> None:
        self.logger.debug('undeclaring queryable %s', topic)
        with self._queryables_lock:
            self._queryables.pop(topic)

    def request(self, key: Key, data: bytes | str | None = None, timeout=1.0) -> Optional[bytes]:
        with self._query_req_sock_lock:
            try:
                # drain socket to avoid getting "late" answers
                flush_queue_sync(self._query_req_sock)

                if isinstance(data, str):
                    data = data.encode()
                elif data is None:
                    data = b''

                req = QueryableEnvelope(ident=key.ident, uuid=random.randbytes(8), topic=key.topic, payload=data)
                # self.logger.debug('requesting %s - %s', key, req)
                self._query_req_sock.send_multipart(req.to_multipart())
                rx = None
                t_start = time.time()
                while (time.time() - t_start) < timeout:
                    try:
                        rx = QueryableEnvelope.from_multipart(self._query_req_sock.recv_multipart())
                    except zmq.Again:
                        continue  # timeout: nothing received, wait longer
                    if rx.uuid == req.uuid:
                        break  # received correct answer
                    else:
                        self.logger.warning(f'request received wrong UUID: {rx.uuid.hex()} vs. {req.uuid.hex()} '
                                            f'for key {key}')
                        rx = None
                        continue
                if rx is not None:
                    # self.logger.debug('Reply received from %s - %s', rx.ident, rx)
                    return rx.payload
                else:
                    self.logger.error(f'request {key} - timeout')
            except Exception as e:
                self.logger.error(f'EX request ({type(e).__name__}): {e}\n{traceback.format_exc()}')

        return None

    def _subscribe_worker(self) -> None:
        logger = logging.getLogger('ZMQ-sub worker')
        sock = create_connect(f'tcp://{self._router_hostname}:{self._ports.DB_ROUTER_PUB_PORT}', zmq, zmq.SUB,
                              timeout_ms=100)
        sock.setsockopt(zmq.RCVHWM, 10000)
        sock.setsockopt(zmq.SNDHWM, 10000)

        while not self._shutdown_ev.is_set():
            try:
                # subscribe to new topics
                if not self._topic_transfer_q.empty():
                    sub_unsub, sub_topic = self._topic_transfer_q.get_nowait()
                    if sub_unsub:
                        sock.subscribe(sub_topic)
                    else:
                        sock.unsubscribe(sub_topic)
                    continue

                topic_bytes, rx_msg = sock.recv_multipart()
                topic = topic_bytes.decode()
                # logger.debug('rx: %s', rx_msg)
                with self._subscribers_lock:
                    for cb in self._subscribers.get(topic):
                        cb[1](topic, rx_msg)
            except zmq.Again:
                continue  # timeout: nothing received
            except Exception as e:
                logger.error(f'EX ({type(e).__name__}): {e}\n{traceback.format_exc()}')

        sock.close()

    def subscribe(self, key: Key, cb: Callable[[str, bytes], None]) -> int:
        with self._subscribers_lock:
            if str(key) not in self._subscribers:
                self._subscribers[str(key)] = []

            sub_id = uuid.uuid4().int
            self._subscribers[str(key)].append((sub_id, cb))

        self._topic_transfer_q.put((True, str(key)))
        return sub_id

    def unsubscribe(self, key: Key, sub_id: int) -> None:
        try:
            with self._subscribers_lock:
                remove_index = None
                for idx, cb in enumerate(self._subscribers[str(key)]):
                    if cb[0] == sub_id:
                        remove_index = idx
                        break
                assert remove_index is not None, f'cannot find subscriber id {sub_id} (key {key})'
                self._subscribers[str(key)].pop(remove_index)

                if len(self._subscribers[str(key)]) == 0:
                    # no callbacks left, unsubscribe
                    self._topic_transfer_q.put((False, str(key)))
        except Exception as e:
            self.logger.error(f'EX unsubscribe ({type(e).__name__}): {e}\n{traceback.format_exc()}')

    def publish(self, key: Key, data: bytes | str) -> None:
        try:
            if isinstance(data, str):
                data_bytes = data.encode()
            else:
                data_bytes = data

            with self._pub_sock_lock:
                self._pub_sock.send_multipart([key.encode(), data_bytes])
        except Exception as e:
            self.logger.error(f'EX publish {key} ({type(e).__name__}): {e}\n{traceback.format_exc()}')


class ConnectionManager(LoggerMixin):
    def __init__(self, *args, router_hostname: str, db_id: str, node_name: str = '',
                 shutdown_event: Optional[threading.Event] = None, **kwargs):
        super().__init__(*args, **kwargs)

        self.env_cfg = environ.to_config(BrokerEnv)

        assert len(router_hostname) > 0, 'CONNECTION_ROUTER environment variable not set'
        self.logger.debug('initializing session with router "%s"', router_hostname)
        self._router_hostname = router_hostname

        assert len(db_id) > 0, 'db_id must not be empty'
        self._db_id = db_id

        self._node_name = node_name

        if shutdown_event is not None:
            self._shutdown_ev = shutdown_event
        else:
            self._shutdown_ev = threading.Event()

        # create RouterConnection to local broker
        self._router_connections_lock = threading.Lock()
        self._router_connections: Dict[str, RouterConnection] = {
            self._db_id: RouterConnection(db_id=self._db_id, router_hostname=self._router_hostname,
                                          node_name=self._node_name)
        }

        # list of databeam IDs and hostnames
        self._dbid_hostnames: Dict[str, str] = {}

        self.initialized = True

    def __del__(self):
        self.logger.debug('del')
        self.close()

    def close(self) -> None:
        self.initialized = False  # TODO race condition when doing s/t else?
        self._shutdown_ev.set()

        # close all RouterConnections
        with self._router_connections_lock:
            for nc in self._router_connections.values():
                nc.close()

        self.logger.info('terminated')

    def set_external_databeams(self, db_ids: List[str], hostnames: List[str]):
        if len(db_ids) != len(hostnames):
            raise ValueError('db_ids and hostnames must have the same length')
        self._dbid_hostnames = dict(zip(db_ids, hostnames))

    def _add_external_router_connection(self, db_id: str):
        assert self._router_connections_lock.locked(), 'router_connections list not locked!'
        # get details for given db-id
        if db_id not in self._dbid_hostnames:
            raise ValueError(f'no known hostname for DBID {db_id}')
        new_connection = RouterConnection(db_id=db_id, router_hostname=self._dbid_hostnames[db_id])
        self._router_connections[db_id] = new_connection

    def declare_queryable(self, key: Key, cb: Callable[[bytes], str | bytes]) -> str:
        assert self.initialized, 'connection manager not initialized'
        assert key.db_id == self._db_id, 'queryable must be declared on our own DBID'
        with self._router_connections_lock:
            return self._router_connections[self._db_id].declare_queryable(key, cb)

    def undeclare_queryable(self, key: str) -> None:
        self.logger.debug('undeclaring queryable %s', key)
        with self._router_connections_lock:
            self._router_connections[self._db_id].undeclare_queryable(key)

    def request(self, key: Key, data: bytes | str | None = None, timeout=1.0) -> Optional[bytes]:
        """
        request something from a queryable
        :param key: Key: describing id, node name and topic
        :param data: bytes | str | None
        :param timeout: float in seconds
        :return: bytes, or None on error / timeout
        """
        assert self.initialized, 'connection manager not initialized'
        assert key.db_id == self._db_id, 'request only allowed to our own DBID'
        with self._router_connections_lock:
            return self._router_connections[self._db_id].request(key, data, timeout)

    def subscribe(self, key: Key, cb: Callable[[str, bytes], None]) -> int:
        assert self.initialized, 'connection manager not initialized'
        self.logger.debug('registering subscriber %s', key)
        with self._router_connections_lock:
            if key.db_id not in self._router_connections:
                self._add_external_router_connection(key.db_id)  # TODO (for all "adds"): raise s/t useful if it fails
            return self._router_connections[key.db_id].subscribe(key, cb)

    def unsubscribe(self, key: Key, sub_id: int) -> None:
        assert self.initialized, 'connection manager not initialized'
        with self._router_connections_lock:
            self._router_connections[key.db_id].unsubscribe(key, sub_id)

    def declare_publisher(self, key: Key) -> int:
        return 0

    def undeclare_publisher(self, pub_id: int) -> None:
        pass

    def publish(self, key: Key, data: bytes | str) -> None:
        assert self.initialized, 'connection manager not initialized'
        assert key.db_id == self._db_id, 'publish only to our own DBID'
        self._router_connections[self._db_id].publish(key, data)


if __name__ == '__main__':
    LoggerMixin.configure_logger(level=os.getenv('LOGLEVEL', 'DEBUG'))
    cm = ConnectionManager(router_hostname='localhost', db_id='dbid', node_name='test', shutdown_event=None)
    logging.info('whee')


    def q_cb(data) -> bytes:
        logging.info(f'q_cb {data}')
        return b'answer'


    i = cm.declare_queryable(Key('dbid', 'c', 'bla'), q_cb)

    # pubs = []
    # i = cm.declare_publisher('pub/bla')
    # pubs.append(i)
    # i = cm.declare_publisher('pub/bla2')
    # pubs.append(i)
    # i = cm.declare_publisher('pub/bla2')
    # pubs.append(i)
    # logging.debug(f'pubs: {pubs}')
    # logging.debug(f'pubs registered: {cm.get_publisher_uuids()}')
    #
    # for i in pubs:
    #     cm.undeclare_publisher(i)
    #     logging.debug(f'pubs registered: {cm.get_publisher_uuids()}')

    cm.close()
    logging.info('done')
