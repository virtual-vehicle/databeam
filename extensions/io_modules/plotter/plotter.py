"""
Live data plotter
"""
import traceback
from typing import Optional, Dict, Union

import environ
import queue

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.data_interface.module_meta_factory import ModuleMetaFactory
from vif.websockets.websocket_api import WebSocketAPI

from io_modules.plotter.server import Server

from io_modules.plotter.config import PlotterConfig

from vif.data_interface.network_messages import Status


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='Plotter')


class Plotter(IOModule):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME
        self.data_broker.capabilities.capture_data = False
        self.data_broker.capabilities.live_data = False

        self._shutdown_queue = queue.Queue()
        self._server: Optional[Server] = None

        self._websocket_api: Optional[WebSocketAPI] = None

        self.logger.debug(self.config_handler.config)

        self.module_interface.live_data_receiver.receive_raw_json_string(True)

    def stop(self):
        self._server.shutdown()
        self._websocket_api.shutdown()
        self.logger.info('module closed')

    def command_get_meta_data(self) -> ModuleMetaFactory:
        config = self.config_handler.config
        meta_cfg = ModuleMetaFactory()
        meta_cfg.add("some_key", "some_data")
        meta_cfg.add_webinterface("Plotter", port=config['port'])

        #for i in range(0, 2):
        #    meta_cfg.add_video_stream(f'Stream {i}', url="stream_url")

        return meta_cfg

    def command_validate_config(self, config) -> Status:
        port = config['port']

        if port % 2 != 0 or port < 6010 or port > 6038:
            return Status(error=True, title="Invalid Port",
                          message='Port must be an even number within range [6010, 6038]')

        return Status(error=False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            if self._server is not None:
                self.module_interface.live_data_receiver.request_live_data([], [])
                self._websocket_api.shutdown()
                self._websocket_api = None
                self._server.shutdown()
                self._server = None

            if self._server is None:
                self._websocket_api = WebSocketAPI(ip="0.0.0.0", port=config['port'] + 1)
                self._websocket_api.start_server()
                #self.live_data_receiver.request_live_data(list(m_dict.keys()), list(m_dict.values()),
                #                                          data_callback=self._live_data_cb)
                self._server = Server(self.module_interface.cm, self.module_interface.db_id, config['port'],
                                      self._shutdown_queue, self.module_interface.live_data_receiver,
                                      self.config_handler, self._websocket_api)

            return Status(error=False)
        except Exception as e:
            self.logger.error(f'error applying config: {type(e).__name__}: {e}\n{traceback.format_exc()}')
            return Status(error=True, title=type(e).__name__, message=str(e))


if __name__ == '__main__':
    main(Plotter, PlotterConfig, environ.to_config(ModuleEnv).MODULE_NAME)
