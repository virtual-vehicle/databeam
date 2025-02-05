import logging
import signal
import threading

import zmq
import environ

from vif.logger.logger import LoggerMixin, log_reentrant


@environ.config(prefix='')
class BrokerEnv:
    LOGLEVEL = environ.var(help='logging level', default='DEBUG')
    DB_ROUTER_FRONTEND_PORT = environ.var(help='DataBeam router queryable frontend port', default='5555')
    DB_ROUTER_BACKEND_PORT = environ.var(help='DataBeam router queryable backend port', default='5556')


class QueryableRouter(LoggerMixin, threading.Thread):
    def __init__(self, cfg: BrokerEnv, shutdown_event: threading.Event):
        threading.Thread.__init__(self)
        LoggerMixin.__init__(self)
        self.cfg = cfg
        self.shutdown_event = shutdown_event

    def run(self):
        frontend = zmq.Context().socket(zmq.ROUTER)
        frontend.setsockopt(zmq.LINGER, 0)
        frontend.setsockopt(zmq.RCVHWM, 100000)
        frontend.setsockopt(zmq.SNDHWM, 100000)
        frontend.bind(f"tcp://*:{self.cfg.DB_ROUTER_FRONTEND_PORT}")

        backend = zmq.Context().socket(zmq.ROUTER)
        backend.setsockopt(zmq.LINGER, 0)
        backend.setsockopt(zmq.RCVHWM, 100000)
        backend.setsockopt(zmq.SNDHWM, 100000)
        backend.bind(f"tcp://*:{self.cfg.DB_ROUTER_BACKEND_PORT}")

        self.logger.info("bound")

        poller = zmq.Poller()
        poller.register(frontend, zmq.POLLIN)
        poller.register(backend, zmq.POLLIN)

        try:
            loglevel = self.logger.getEffectiveLevel()

            while not self.shutdown_event.is_set():
                socks = dict(poller.poll(100))
                if socks.get(frontend) == zmq.POLLIN:
                    x = frontend.recv_multipart()
                    if loglevel <= logging.DEBUG:
                        self.logger.debug(f"rx FRONTend: {x[3].decode()} from {x[0].decode()} - {x}")
                    x[0], x[1] = x[1], x[0]
                    backend.send_multipart(x)
                if socks.get(backend) == zmq.POLLIN:
                    x = backend.recv_multipart()
                    if loglevel <= logging.DEBUG:
                        self.logger.debug(f"rx BACKend: {x[3].decode()} from {x[0].decode()} - {x}")
                    x[0], x[1] = x[1], x[0]
                    frontend.send_multipart(x)
        except Exception as e:
            self.logger.error(f'EX: {type(e).__name__}: {e}')

        frontend.close()
        backend.close()


if __name__ == '__main__':
    logger_main = logging.getLogger('queryable_router')

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

    shutdown_ev = threading.Event()

    for sig in signal.valid_signals():
        try:
            signal.signal(sig, lambda signum, frame: log_reentrant(f'UNHANDLED signal {signum} called'))
        except OSError:
            pass

    # ignore child signal
    signal.signal(signal.SIGCHLD, lambda signum, frame: log_reentrant(f'ignoring signal {signum}'))

    # handle shutdown signals
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda signum, frame: (shutdown_ev.set(),
                                                  log_reentrant(f'signal {signum} called -> shutdown!')))

    logger_main.info('starting')
    router_queryables = QueryableRouter(env_cfg, shutdown_ev)
    router_queryables.start()

    shutdown_ev.wait()

    router_queryables.join()

    num_threads_left = threading.active_count() - 1
    logger_main.debug(f'done - threads left: {num_threads_left}')
    if num_threads_left > 0:
        logger_main.info(f'threads left: {[thread.name for thread in threading.enumerate()]}')
