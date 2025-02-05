import os

_import_cm_lib = os.getenv('DB_CM_LIB', 'ZMQ')
if _import_cm_lib == 'ZENOH':
    from vif.data_interface.connection_manager_zenoh import *
elif _import_cm_lib == 'ZMQ':
    from vif.data_interface.connection_manager_zmq import *
else:
    raise ImportError(f'Unknown connection manager library: {_import_cm_lib}')
