import zmq
import zmq.asyncio

from vif.network.network import resolve_uri


def create_connect(uri: str, zmq_instance, mode, identity=b'', resolve=False, timeout_ms: int = -1) -> zmq.Socket:
    """
    Create a zmq socket connecting to an uri
    :param uri: the uri to connect to
    :param zmq_instance: either zmq, zmq.green or zmq.asyncio
    :param mode: any of zmq.{REQ, REP, PUSH, PULL, PUB, SUB, XPUB, XSUB}
    :param identity: optional identity bytes
    :param resolve: whether to resolve the given uri
    :param timeout_ms: ms, -1: blocking, 0: return immediately, other: timeout with zmq.Again exception
    :return: the created socket
    """
    if resolve:
        uri = resolve_uri(uri)

    sock = zmq_instance.Context.instance().socket(mode)
    # noinspection PyUnresolvedReferences
    sock.setsockopt(zmq.LINGER, 0)
    if len(identity) > 0:
        sock.setsockopt(zmq.IDENTITY, identity)
    if timeout_ms >= 0:
        sock.setsockopt(zmq.RCVTIMEO, timeout_ms)
    sock.connect(uri)

    return sock


def create_bind(uri: str, zmq_instance, mode, resolve=False, timeout_ms: int = -1) -> zmq.Socket:
    """
    Create a zmq socket binding to an uri
    :param uri: the uri to bind to
    :param zmq_instance: either zmq, zmq.green or zmq.asyncio
    :param mode: any of zmq.{REQ, REP, PUSH, PULL, PUB, SUB, XPUB, XSUB}
    :param resolve: whether to resolve the given uri
    :param timeout_ms: set custom socket timeout
    :return: the created socket
    """
    if resolve:
        uri = resolve_uri(uri)

    sock = zmq_instance.Context.instance().socket(mode)
    # noinspection PyUnresolvedReferences
    sock.setsockopt(zmq.LINGER, 0)
    if timeout_ms >= 0:
        sock.setsockopt(zmq.RCVTIMEO, timeout_ms)
    sock.bind(uri)

    return sock


def msg_available(socket) -> bool:
    if socket.getsockopt(zmq.EVENTS) & zmq.POLLIN:
        return True
    return False


async def flush_queue(zmq_socket: zmq.asyncio.Socket):
    while zmq_socket.getsockopt(zmq.EVENTS) & zmq.POLLIN:
        _ = await zmq_socket.recv()


def flush_queue_sync(zmq_socket: zmq.Socket):
    while zmq_socket.getsockopt(zmq.EVENTS) & zmq.POLLIN:
        _ = zmq_socket.recv()
