import json
from typing import Dict, List, Callable, Tuple, Optional
from functools import partial

from vif.logger.logger import LoggerMixin
from vif.data_interface.connection_manager import ConnectionManager, Key


class LiveDataReceiver(LoggerMixin):
    def __init__(self, *args, con_mgr: ConnectionManager, databeam_id: str, **kwargs):
        super().__init__(*args, **kwargs)

        self._cm = con_mgr
        # dict of subscriptions: key = topic, value = (sub_id: int, sub_all: bool)
        self._subs: Dict[str, Tuple[int, bool, Key]] = {}
        self._db_id = databeam_id
        self._data_callback: Optional[Callable[[str, str, Dict | str], None]] = None
        self._raw_json_string = False

    def receive_raw_json_string(self, enabled: bool):
        self._raw_json_string = enabled

    def request_live_data(self, modules: List[str], sub_all: Optional[List[bool]] = None,
                          data_callback: Optional[Callable[[str, str, Dict | str], None]] = None,
                          db_ids: Optional[List[str]] = None) -> None:
        """
        Register callback for live data.

        :param modules: list of module names
        :param sub_all: list of boolean for each module:
                        True -> subscribe for all data, False -> subscribe for fixed-rate data
        :param data_callback: callback function: def data_callback(module_name: str, data: Dict) -> None
        :param db_ids: optional list of databeam ids (used to receive remote data)
        """
        sub_all = [False] * len(modules) if sub_all is None else sub_all
        db_ids = [self._db_id] * len(modules) if db_ids is None else db_ids
        assert len(modules) == len(sub_all)
        assert len(modules) == len(db_ids)

        # create a list of new subscriptions: dbid/module
        new_subs = [f'{db_id}/{module}' for db_id, module in zip(db_ids, modules)]

        # create dict to check for changed sub-modes: {id/module: bool} (True = subscribe all, False = fixed rate)
        modules_topic = {new_subs[x]: sub_all[x] for x in range(len(new_subs))}

        # list of keys of self._subs: IF key not in modules_topic OR sub bool does not match
        remove_list = [k for k, v in self._subs.items() if k not in modules_topic.keys() or v[1] != modules_topic[k]]

        # remove unused subscriptions
        for t in remove_list:
            self._cm.unsubscribe(self._subs[t][0])
            del self._subs[t]

        # subscribe for new modules
        for m, s_all, db_id in zip(modules, sub_all, db_ids):
            sub_key = f'{db_id}/{m}'
            if sub_key not in self._subs.keys():
                topic = Key(db_id, f'm/{m}', 'liveall' if s_all else 'livedec')
                sub_id = self._cm.subscribe(topic, partial(self._data_received, db_id, m))
                self._subs[sub_key] = (sub_id, s_all, topic)

        # log subscriptions
        log_data = [[k, "all" if v[1] else "fixed"] for k, v in self._subs.items()]
        self.logger.info("Receive Live Data: %s", str(log_data))

        # register callback
        self._data_callback = data_callback

    def shutdown(self):
        self.logger.debug('shutting down')
        for value in self._subs.values():
            self._cm.unsubscribe(value[0])
        self._subs.clear()

    def _data_received(self, db_id: str, module_name: str, key: str, data: bytes) -> None:
        live_json = data.decode()
        # self.logger.debug('%s/%s data: %s', db_id, module_name, live_json)

        # parse json
        if self._raw_json_string:
            data_out = live_json
        else:
            try:
                data_out = json.loads(live_json)
            except Exception as e:
                self.logger.error(f'EX data_received (json.loads {live_json}) - {type(e).__name__}: {e}')
                return

        # invoke data callback
        if self._data_callback is not None:
            self._data_callback(db_id, module_name, data_out)
