"""
Gunicorn configuration for DataBeam REST API.
Uses single worker to maintain singleton API instances.
"""
import logging

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes - MUST be 1 to maintain singleton APIs: ControllerAPI, PreviewAPI, FileAPI, and WebSocketAPI
workers = 1
worker_class = "sync"
worker_connections = 1000  # not used in sync mode
max_requests = 0  # Disable worker restart (0 = unlimited)
max_requests_jitter = 0
timeout = 0  # Request timeout for long-running operations
graceful_timeout = 15  # Time to wait for workers to finish shutdown
keepalive = 5

# Logging
errorlog = "-"  # Log to stderr
loglevel = "info"
accesslog = None  # disable access log
# accesslog = "-"  # Log to stdout
# access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "databeam-rest-api"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# IMPORTANT: Do NOT preload app because ZeroMQ sockets cannot survive fork()
# All initialization must happen in worker process after fork (post_worker_init)
preload_app = False


def set_log_format(module, id_str: str):
    # Set up custom log format to match application logs
    # Format: YYYY-MM-DD HH:MM:SS,mmm LEVEL    LOGGER-NAME | MESSAGE
    log_format = f'%(asctime)s %(levelname)-7s Gunicorn {id_str} | %(message)s'
    formatter = logging.Formatter(log_format)

    # Apply formatter to all handlers of the error log
    for handler in module.log.error_log.handlers:
        handler.setFormatter(formatter)


# Hooks of parent gunicorn process
def on_starting(server):
    """Called just before the master process is initialized."""
    set_log_format(server, "main")
    server.log.info("Starting Gunicorn server for DataBeam REST API")


# Hooks of child gunicorn process / our flask
def post_worker_init(worker):
    """Called after a worker has been initialized."""
    set_log_format(worker, "worker")
