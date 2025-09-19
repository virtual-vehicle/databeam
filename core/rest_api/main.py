"""
Starts the Rest API and WebGUI.
"""
import secrets
import threading
from pathlib import Path
import queue
import signal
import logging

import environ

from vif.logger.logger import LoggerMixin, log_reentrant
from vif.websockets.websocket_api import WebSocketAPI

from controller_api import ControllerAPI
from file_api import FileAPI
from server import Server
from preview_api import PreviewAPI


@environ.config(prefix='')
class RestEnv:
    LOGLEVEL = environ.var(help='logging level', default='DEBUG')
    # CONFIG_DIR = environ.var(help='config root directory', converter=lambda x: Path(x).expanduser())
    DATA_DIR = environ.var(help='data directory', converter=lambda x: Path(x).expanduser(),
                           default='/opt/databeam/data')
    LOGS_DIR = environ.var(help='logs directory', converter=lambda x: Path(x).expanduser(),
                           default='/opt/databeam/logs')
    DEPLOY_VERSION = environ.var(help='docker images tag', default='latest')
    DB_ID = environ.var(help='databeam domain name for communication', default='db')
    DB_ROUTER = environ.var(help='DataBeam router hostname to find other nodes', default='localhost')
    # separate multiple usernames or passwords with '#'
    LOGIN_USER_NAMES = environ.var(help='User names for login', default='databeam')
    # create password hashes with
    # hashlib.sha256("plaintext".encode('utf-8')).hexdigest()
    # or
    # echo -n "plaintext" | sha256sum | tr -d "[:space:]-"
    LOGIN_PASSWORD_HASHES = environ.var(help='sha256 hash of rest api password as hex string')
    # optionally provide an external secret key (https://flask.palletsprojects.com/en/stable/quickstart/#sessions)
    SECRET_KEY = environ.var(help='secret key for flask', default=secrets.token_hex())


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    env_cfg = environ.to_config(RestEnv)

    LoggerMixin.configure_logger(level=env_cfg.LOGLEVEL)
    logger_main = logging.getLogger('REST-main')

    shutdown_queue = queue.Queue()
    shutdown_ev = threading.Event()

    for sig in signal.valid_signals():
        try:
            signal.signal(sig, lambda signum, frame: log_reentrant(f'UNHANDLED signal {signum} called'))
        except OSError:
            pass

    # ignore child signal
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)

    # handle shutdown signals
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda signum, frame: (shutdown_ev.set(), shutdown_queue.put("shutdown"),
                                                  log_reentrant(f'signal {signum} called -> shutdown!')))

    # create websocket server
    websocket_api = WebSocketAPI(ip="0.0.0.0", port=5001)

    # create connection to databeam controller
    controller_api = ControllerAPI(databeam_id=env_cfg.DB_ID, websocket_api=websocket_api, shutdown_ev=shutdown_ev,
                                   db_router=env_cfg.DB_ROUTER)
    controller_api.start()

    file_api = FileAPI(data_dir=env_cfg.DATA_DIR / env_cfg.DEPLOY_VERSION,
                       logs_dir=env_cfg.LOGS_DIR / env_cfg.DEPLOY_VERSION)

    logger_main.info('Modules: %s', str(controller_api.get_modules_dict()))
    logger_main.info('Data Configs: %s', str(controller_api.get_modules_and_data_config_dict()))
    #print(str(controller_api.get_measurement_state_dict()))
    # data_config = controller_api.get_data_config_dict("Ping")
    # logger_main.debug("Ping Data Config: " + str(data_config))
    #set_meta = controller_api.set_metadata_strings(metadata['system_meta_json'], metadata['user_meta_json'])
    #print("SET META: " + str(set_meta))

    # start websocket server
    websocket_api.start_server()

    # create preview api
    preview_api = PreviewAPI(controller_api=controller_api, websocket_api=websocket_api)
    preview_api.start()

    # start server
    flask_server = Server(controller_api=controller_api, file_api=file_api, preview_api=preview_api,
                          shutdown_queue=shutdown_queue, login_user_names_str=env_cfg.LOGIN_USER_NAMES,
                          login_password_hashes_str=env_cfg.LOGIN_PASSWORD_HASHES,
                          data_dir=env_cfg.DATA_DIR / env_cfg.DEPLOY_VERSION,
                          logs_dir=env_cfg.LOGS_DIR / env_cfg.DEPLOY_VERSION,
                          secret_key=env_cfg.SECRET_KEY)

    # wait for signals
    shutdown_ev.wait()

    # print shutdown message
    logger_main.info("Shutdown servers ...")

    # shutdown server
    preview_api.shutdown()
    flask_server.shutdown()
    websocket_api.shutdown()
    controller_api.shutdown()

    num_threads_left = threading.active_count() - 1
    logger_main.debug(f'done - threads left: {num_threads_left}')
    if num_threads_left > 0:
        logger_main.info(f'threads left: {[thread.name for thread in threading.enumerate()]}')
