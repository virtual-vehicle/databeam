"""
Unified entry point for the Rest API and WebGUI.
Supports both development mode (python main.py) and production mode (gunicorn).
"""
import atexit
import secrets
import threading
import traceback
from pathlib import Path
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
    LOGIN_PASSWORD_HASHES = environ.var(help='sha256 hash of rest api password as hex string',
                                        default='37a8eec1ce19687d132fe29051dca629d164e2c4958ba141d5f4133a33f0688f')
    # optionally provide an external secret key (https://flask.palletsprojects.com/en/stable/quickstart/#sessions)
    SECRET_KEY = environ.var(help='secret key for flask', default=secrets.token_hex())


def exit_thread_check(logger: logging.Logger):
    num_threads_left = threading.active_count() - 1
    logger.debug(f'done - threads left: {num_threads_left}')
    if num_threads_left > 0:
        logger.info(f'threads left: {[thread.name for thread in threading.enumerate()]}')


def initialize():
    # Load environment configuration
    env_cfg = environ.to_config(RestEnv)

    # Configure logging
    LoggerMixin.configure_logger(level=env_cfg.LOGLEVEL)
    logger = logging.getLogger('REST-main')

    # Create shutdown handling events
    shutdown_ev = threading.Event()
    shutdown_done_ev = threading.Event()

    # Initialize singleton services at module level
    logger.info("Initializing singleton services...")

    # Create websocket server
    websocket_api = WebSocketAPI(ip="0.0.0.0", port=5001)

    # Create connection to databeam controller
    controller_api = ControllerAPI(
        databeam_id=env_cfg.DB_ID,
        websocket_api=websocket_api,
        shutdown_ev=shutdown_ev,
        db_router=env_cfg.DB_ROUTER
    )

    # Create file API
    file_api = FileAPI(
        data_dir=env_cfg.DATA_DIR / env_cfg.DEPLOY_VERSION,
        logs_dir=env_cfg.LOGS_DIR / env_cfg.DEPLOY_VERSION
    )

    # Create preview api
    preview_api = PreviewAPI(
        controller_api=controller_api,
        websocket_api=websocket_api
    )

    # Create Flask server
    flask_server = Server(
        controller_api=controller_api,
        file_api=file_api,
        preview_api=preview_api,
        login_user_names_str=env_cfg.LOGIN_USER_NAMES,
        login_password_hashes_str=env_cfg.LOGIN_PASSWORD_HASHES,
        data_dir=env_cfg.DATA_DIR / env_cfg.DEPLOY_VERSION,
        logs_dir=env_cfg.LOGS_DIR / env_cfg.DEPLOY_VERSION,
        secret_key=env_cfg.SECRET_KEY,
        use_internal_server=True if __name__ == '__main__' else False
    )

    # Expose the Flask app for Gunicorn
    app = flask_server.app

    def shutdown_services():
        logger.info("Shutting down services...")
        shutdown_ev.set()
        try:
            preview_api.shutdown()
            flask_server.shutdown()
            websocket_api.shutdown()
            controller_api.shutdown()
            logger.info("All services shut down successfully")
        except Exception as e:
            logger.error(f"Error during service shutdown: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        shutdown_done_ev.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        # make sure not to overwrite gunicorn signal handlers
        original_handler = signal.getsignal(sig)
        signal.signal(sig, lambda signum, frame: (
            log_reentrant(f'WHEE signal {signum} called -> shutdown!'),
            threading.Thread(target=shutdown_services, daemon=True).start(),
            original_handler(signum, frame) if callable(original_handler) else None
        ))

    atexit.register(lambda: (
        logger.info("Waiting for shutdown to finish..."),
        shutdown_done_ev.wait(),
        exit_thread_check(logger),
        logger.info("Shutdown done.")
    ))

    logger.info("Starting background services...")
    controller_api.start()
    logger.info('Modules: %s', str(controller_api.get_modules_dict()))
    logger.info('Data Configs: %s', str(controller_api.get_modules_and_data_config_dict()))
    websocket_api.start_server()
    preview_api.start()

    logger.info("All background services started successfully")

    if __name__ == '__main__':
        # return event for development mode
        return shutdown_ev
    else:
        # return app for gunicorn
        return app


if __name__ == '__main__':
    shutdown_ev = initialize()
    shutdown_ev.wait()
