import json
import threading
from typing import Optional, Dict
import queue
import logging

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from werkzeug.serving import make_server

from vif.data_interface.config_handler import ConfigHandler

from vif.data_interface.live_data_receiver import LiveDataReceiver
#from vif.websockets.websocket_api import WebSocketAPI
from vif.websockets.asyncwebsocket_api import AsyncWebSocketAPI
from vif.data_interface.connection_manager import ConnectionManager, Key

from vif.data_interface.network_messages import ModuleRegistryQueryCmd, ModuleRegistryQuery, ModuleRegistryReply

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


class Server:
    def __init__(self, cm: ConnectionManager, databeam_id, port: int, shutdown_queue, live_data_receiver: LiveDataReceiver,
                 config_handler: ConfigHandler, websocket_api: AsyncWebSocketAPI):
        self.logger = logging.getLogger('Server')
        self.cm = cm
        self._databeam_id = databeam_id
        self._live_data_receiver = live_data_receiver
        self._websocket_api = websocket_api
        self._config = config_handler.config
        self._config_handler = config_handler

        self._shutdown_queue: queue.Queue = shutdown_queue

        self._worker_thread: Optional[threading.Thread] = None
        self._thread_event = threading.Event()

        self._client_id_counter = 0

        self._cfg = {
            'port': port
        }

        self.app: Flask = Flask("RPI Server")
        CORS(self.app)
        self.app.add_url_rule('/', 'home', self.route_home, methods=['GET'])
        self.app.add_url_rule('/modules', 'modules', self.route_get_modules, methods=['GET'])
        self.app.add_url_rule('/requested_modules', 'requested_modules',
                              self.route_requested_modules, methods=['POST'])
        self.app.add_url_rule('/config', 'config', self.route_config, methods=['GET'])
        self.app.add_url_rule('/set_config', 'set_config', self.route_set_config, methods=['POST'])
        self._server = make_server('0.0.0.0', self._cfg['port'], self.app)
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.start()
        self.logger.debug("Server Running")

    def _live_data_cb(self, db_id: str, module_name: str, data: Dict):
        self._websocket_api.broadcast_json_str("data/" + module_name, data)

    def route_home(self):
        return render_template('index.html')

    def route_get_modules(self):
        return jsonify(self.get_modules())

    def route_config(self):
        return jsonify({'config': self._config_handler.config})

    def route_set_config(self):
        config = request.json['config']
        self._config_handler.write_config(config)
        return jsonify({'result': 'ok'})

    def route_requested_modules(self):
        modules = request.json['modules']
        live_sources = request.json['live_sources']
        self.logger.info("Requested modules: " + str(modules))
        self._live_data_receiver.request_live_data(modules, [x == "All" for x in live_sources], self._live_data_cb)
        return jsonify(modules)

    def shutdown(self):
        self._server.shutdown()
        self.logger.debug("Server Closed.")

    def get_modules(self):
        message = ModuleRegistryQuery(cmd=ModuleRegistryQueryCmd.LIST)
        reply = self.cm.request(Key(self._databeam_id, 'c', 'module_registry'), message.serialize())
        value = ModuleRegistryReply.deserialize(reply)
        modules_dict = value.get_dict()

        modules_list = [x['name'] for x in modules_dict['modules'] if x['name'] != 'Plotter']

        meta_dict = {}
        topics_dict = {}

        for module in modules_list:
            meta_dict[module] = self.get_module_meta(module)
            topics_dict[module] = self.get_module_schemas(module)

        self.logger.debug({'modules': modules_list, 'meta': meta_dict, 'topics': topics_dict})
        return {'modules': modules_list, 'meta': meta_dict}

    def get_module_meta(self, module_name):
        try:
            reply = self.cm.request(Key(self._databeam_id, f'm/{module_name}', 'get_metadata'))
            return json.loads(reply)
        except:
            return {}

    def get_module_schemas(self, module_name):
        try:
            reply = self.cm.request(Key(self._databeam_id, f'm/{module_name}', 'get_schemas'))
            topic_names = json.loads(reply)['topic_names']
            return topic_names
        except:
            return []
