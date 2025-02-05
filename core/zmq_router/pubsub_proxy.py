import logging
import signal
import threading

import zmq
import environ

from vif.logger.logger import LoggerMixin, log_reentrant


@environ.config(prefix='')
class BrokerEnv:
    LOGLEVEL = environ.var(help='logging level', default='DEBUG')
    DB_ROUTER_SUB_PORT = environ.var(help='DataBeam router SUB port', default='5557')
    DB_ROUTER_PUB_PORT = environ.var(help='DataBeam router PUB port', default='5558')


if __name__ == '__main__':
    logger_main = logging.getLogger('pubsub_proxy')

    # load environ config
    try:
        env_cfg = environ.to_config(BrokerEnv)
    except environ.MissingEnvValueError as e_main:
        logger_main.error('Missing environment variable: %s', e_main)
        exit(1)
    except Exception as e_main:
        logger_main.error(e_main)
        exit(1)

    LoggerMixin.configure_logger(level=env_cfg.LOGLEVEL)
    logger_main.info('starting')

    sock_sub = zmq.Context().socket(zmq.XSUB)
    sock_sub.setsockopt(zmq.LINGER, 0)
    sock_sub.setsockopt(zmq.RCVHWM, 100000)
    sock_sub.setsockopt(zmq.SNDHWM, 100000)
    sock_sub.bind(f"tcp://*:{env_cfg.DB_ROUTER_SUB_PORT}")

    sock_pub = zmq.Context().socket(zmq.XPUB)
    sock_pub.setsockopt(zmq.LINGER, 0)
    sock_pub.setsockopt(zmq.RCVHWM, 100000)
    sock_pub.setsockopt(zmq.SNDHWM, 100000)
    sock_pub.bind(f"tcp://*:{env_cfg.DB_ROUTER_PUB_PORT}")

    logger_main.info("bound")

    def handle_term_signal(signum, frame):
        log_reentrant(f'signal {signum} called -> shutdown!')
        raise KeyboardInterrupt

    # Register the handler for the TERM signal
    signal.signal(signal.SIGTERM, handle_term_signal)

    try:
        proxy = zmq.proxy(sock_sub, sock_pub)
        # we never get here ...
    except KeyboardInterrupt:
        logger_main.info('shutting down')
    except Exception as e:
        logger_main.error(f'EX: {type(e).__name__}: {e}')

    num_threads_left = threading.active_count() - 1
    logger_main.debug(f'done - threads left: {num_threads_left}')
    if num_threads_left > 0:
        logger_main.info(f'threads left: {[thread.name for thread in threading.enumerate()]}')
