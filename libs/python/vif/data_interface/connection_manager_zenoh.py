import json
import logging
import threading
import time
import traceback
import uuid
from importlib.metadata import version as package_version
from typing import List, Dict, Tuple, Callable, Any, Optional
from functools import partial
import os

from vif.logger.logger import LoggerMixin

import zenoh


class ConnectionException(Exception):
    pass

class ConnectionManager(LoggerMixin):
    def __init__(self, *args, router_hostname, db_id: str = '', node_name: str = '',
                 shutdown_event: Optional[threading.Event] = None, **kwargs):
        super().__init__(*args, **kwargs)

        # keep a list of registered declarations
        # dict-key = uuid --> queryable
        self._queryables: Dict[str, zenoh.Queryable] = {}
        # dict-key = key --> tuple(pub, list of uuids)
        self._publishers: Dict[str, Tuple[zenoh.Publisher, List[int]]] = {}
        # dict-key = uuid --> tuple(sub, key)
        self._subscribers: Dict[int, Tuple[zenoh.Subscriber, str]] = {}

        assert len(router_hostname) > 0, 'DB_ROUTER environment variable not set'
        self.logger.debug('initializing zenoh (version %s) session with router "%s:7447"',
                          package_version('eclipse-zenoh'), router_hostname)
        # zenoh.init_logger()
        zenoh.try_init_log_from_env()
        z_config = zenoh.Config()
        # 'client' mode: communicate brokered over zenoh-router | 'peer' mode: peer-to-peer mesh
        z_config.insert_json5('mode', json.dumps('client'))
        # disable multicast-scouting and rely on router to connect peers
        z_config.insert_json5('scouting/multicast/enabled', json.dumps(False))
        # router will gossip peer addresses to newly connected peers to allow mesh communication
        z_config.insert_json5('scouting/gossip/enabled', json.dumps(True))
        z_config.insert_json5('scouting/gossip/multihop', json.dumps(True))
        # z_config.insert_json5('transport/link/tx/queue/backoff', json.dumps(100))
        # add endpoint to connect to router
        z_config.insert_json5('connect/endpoints', json.dumps([f"tcp/{router_hostname}:7447"]))
        z_config.insert_json5('listen/endpoints', json.dumps(["tcp/[::]:0"]))
        tries = 0
        self._zs = None
        # try to connect a few times or wait for shutdown-event if given
        while not shutdown_event.is_set() if shutdown_event is not None else tries <= 3:
            tries += 1
            try:
                self._zs = zenoh.open(z_config)
                break
            except zenoh.ZError as e:
                self.logger.error(f'Zenoh open failed: {e}')
                if shutdown_event is not None:
                    shutdown_event.wait(timeout=1)
                else:
                    time.sleep(0.5)
        if self._zs is None:
            raise ConnectionException(f'Zenoh open failed after {tries} tries')

        # info = self._zs.info
        # self.logger.debug(f"INIT zid: {info.zid()} routers: {info.routers_zid()} peers: {info.peers_zid()}")

        self._zs_backup_reference = self._zs  # keep reference to zenoh session and call destructor when closed
        self.initialized = True

    def __del__(self):
        self.logger.debug('del')
        self.close()

    def close(self):
        self.initialized = False

        if self._zs is None:
            return

        if len(self._queryables) or len(self._publishers) or len(self._subscribers):
            self.logger.debug('undeclaring')

        # unregister queryables and publishers
        for q in self._queryables.values():
            q.undeclare()
        self._queryables.clear()
        for p in self._publishers.values():
            p[0].undeclare()
        self._publishers.clear()
        for s in self._subscribers.values():
            s[0].undeclare()
        self._subscribers.clear()

        if self._zs is not None:
            self.logger.debug('closing')
            # self._zs.delete(f'{self.db_id}/m/{self.name}/**')
            self._zs.close()
            self.logger.debug('closed')
        self._zs = None
        self.logger.info('terminated')

    def get_publisher_uuids(self) -> Dict[str, List[int]]:
        return {k: v[1] for k, v in self._publishers.items()}

    def _query_cb(self, query, _cm_key, _cm_cb, *args, **kwargs):
        reply = _cm_cb(*args, data=bytes(query.payload) if query.payload is not None else None, **kwargs)
        if isinstance(reply, str):
            reply = reply.encode()
        try:
            assert isinstance(reply, bytes), 'return type of callback must be bytes'
        except AssertionError as e:
            self.logger.error(f'EX {e}: {_cm_cb.__name__}')

        try:
            query.reply(key_expr=str(_cm_key), payload=reply)
        except Exception as e:
            self.logger.error(f'EX reply ({type(e).__name__}): {e}\n{traceback.format_exc()}')

    def declare_queryable(self, key: str, cb: Callable[[bytes], str | bytes]) -> str:
        assert self.initialized, 'connection manager not initialized'
        self.logger.debug('registering queryable %s', key)
        assert key not in self._queryables, f'queryable {key} already registered'
        self._queryables[key] = self._zs.declare_queryable(key_expr=key,
                                                           handler=partial(self._query_cb, _cm_key=key, _cm_cb=cb),
                                                           complete=True)  # declare, that we can answer what's coming
        return key

    def undeclare_queryable(self, q_id):
        self.logger.debug('undeclaring queryable %d', q_id)
        self._queryables[q_id].undeclare()
        self._queryables.pop(q_id)

    @staticmethod
    def _sub_cb(sample: zenoh.Sample, _cm_key, _cm_cb, *args, **kwargs):
        _cm_cb(_cm_key, *args, data=bytes(sample.payload) if sample.payload is not None else None, **kwargs)

    def subscribe(self, key, cb: Callable[[str, bytes], None]) -> int:
        assert self.initialized, 'connection manager not initialized'
        self.logger.debug('registering subscriber %s', key)
        sub = self._zs.declare_subscriber(key, partial(self._sub_cb, _cm_key=key, _cm_cb=cb))
        sub_id = uuid.uuid4().int
        self._subscribers[sub_id] = (sub, key)
        return sub_id
    
    def unsubscribe(self, sub_id):
        self.logger.debug('unregistering subscriber key %s', self._subscribers[sub_id][1])
        self._subscribers[sub_id][0].undeclare()
        self._subscribers.pop(sub_id)

    def declare_publisher(self, key) -> int:
        assert self.initialized, 'connection manager not initialized'
        pub_id = uuid.uuid4().int
        if key in self._publishers:
            self.logger.debug('registering publisher id %d to existing key', pub_id)
            self._publishers[key][1].append(pub_id)
        else:
            self.logger.debug('adding publisher id %d', pub_id)
            pub = self._zs.declare_publisher(key, congestion_control=zenoh.CongestionControl.BLOCK,
                                             reliability=zenoh.Reliability.RELIABLE)
            self._publishers[key] = (pub, [pub_id])
        return pub_id

    def undeclare_publisher(self, pub_id: int):
        self.logger.debug('unregistering publisher id %d', pub_id)
        # find key for unique pub_id
        key = None
        for k, v in self._publishers.items():
            if pub_id in v[1]:
                key = k
                break
        if key is not None:
            # remove uuid from list
            self._publishers[key][1].remove(pub_id)
            # undeclare publisher if list is empty
            if len(self._publishers[key][1]) == 0:
                self.logger.debug('undeclaring publisher %s', key)
                self._publishers[key][0].undeclare()
                self._publishers.pop(key)
        else:
            self.logger.error('cannot find publisher id %d', pub_id)

    def request(self, key: Tuple[str, str], data: bytes | str | None = None, timeout=1) -> Optional[bytes]:
        assert self.initialized, 'connection manager not initialized'
        try:
            key = ''.join(key)
            reply = next(self._zs.get(key, payload=data, timeout=timeout,
                                      target=zenoh.QueryTarget.BEST_MATCHING,
                                      congestion_control=zenoh.CongestionControl.BLOCK,
                                      consolidation=zenoh.ConsolidationMode.NONE))
            if reply.ok is not None:
                return bytes(reply.ok.payload)
            else:
                self.logger.error(f'request {key} received Error: "{reply.err.payload.to_string()}"')
        except StopIteration:
            self.logger.error(f'request failed - no response for {key}')
        except Exception as e:
            self.logger.error(f'EX request ({type(e).__name__}): {e}\n{traceback.format_exc()}')
        # info = self._zs.info
        # self.logger.debug(f"zid: {info.zid()} routers: {info.routers_zid()} peers: {info.peers_zid()}")
        return None

    def publish(self, key, data):
        assert self.initialized, 'connection manager not initialized'
        try:
            self._publishers[key][0].put(payload=data)
        except Exception as e:
            self.logger.error(f'EX publish ({type(e).__name__}): {e}\n{traceback.format_exc()}')


if __name__ == '__main__':
    LoggerMixin.configure_logger(level=os.getenv('LOGLEVEL', 'DEBUG'))
    cm = ConnectionManager(router_hostname='bla', shutdown_event=None)
    logging.info('whee')

    pubs = []
    i = cm.declare_publisher('pub/bla')
    pubs.append(i)
    i = cm.declare_publisher('pub/bla2')
    pubs.append(i)
    i = cm.declare_publisher('pub/bla2')
    pubs.append(i)
    logging.debug(f'pubs: {pubs}')
    logging.debug(f'pubs registered: {cm.get_publisher_uuids()}')

    for i in pubs:
        cm.undeclare_publisher(i)
        logging.debug(f'pubs registered: {cm.get_publisher_uuids()}')

    cm.close()
    logging.info('done')
