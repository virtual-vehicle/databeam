import threading
import traceback
from typing import Optional


from vif.data_interface.connection_manager import ConnectionManager, Key
from vif.data_interface.network_messages import MeasurementState


def ping_controller(cm: ConnectionManager, db_id: str, module_name: str = '') -> bool:
    reply = cm.request(Key(db_id, 'c', 'ping'), data=module_name.encode('utf-8'), timeout=1)
    if reply is not None and reply.decode("utf-8") == "pong":
        return True
    return False


def wait_for_controller(logger, shutdown_ev: threading.Event, cm: ConnectionManager, db_id: str):
    while not shutdown_ev.is_set():
        logger.debug('trying connection to controller with ID: %s', db_id)
        try:
            if ping_controller(cm, db_id):
                logger.info('connection to controller established')
                break
        except Exception as e:
            logger.error(f'wait_for_controller ({type(e).__name__}): {e}\n{traceback.format_exc()}')
        shutdown_ev.wait(1)


def get_measurement_state(logger, cm: ConnectionManager, db_id: str) -> Optional[MeasurementState]:
    try:
        reply = cm.request(Key(db_id, 'c', 'get_state'))
        value = MeasurementState.deserialize(reply)
        if value is not None:
            logger.info('get_measurement_state: %s', value.serialize())
            return value
    except Exception as e:
        logger.error(f'get_measurement_state ({type(e).__name__}): {e}\n{traceback.format_exc()}')
    return None
