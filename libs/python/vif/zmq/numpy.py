import numpy
import zmq.asyncio
from typing import Tuple, Mapping
import msgpack

# https://pyzmq.readthedocs.io/en/latest/serialization.html


async def send_numpy_array(socket: zmq.asyncio.Socket, array: numpy.ndarray, args_dict: Mapping = None, topic: str = '',
                           flags=0, copy=True, track=False) -> None:
    """
    Send a numpy array through a zmq socket
    :param socket: the zmq socket
    :param array: array to be sent
    :param args_dict optional mapping of additional arguments
    :param topic: optional message prefix (PUB / SUB)
    :param flags: :meth `zmq.Socket.send`
    :param copy: :meth `zmq.Socket.send`
    :param track: :meth `zmq.Socket.send`
    """
    if topic:
        socket.send_string(topic, flags | zmq.SNDMORE)
    if args_dict:
        args_dict_packed = msgpack.packb(args_dict)
    else:
        args_dict_packed = msgpack.packb({})
    socket.send(args_dict_packed, flags | zmq.SNDMORE)
    md_packed = msgpack.packb(dict(dtype=str(array.dtype), shape=array.shape))
    socket.send(md_packed, flags | zmq.SNDMORE)
    return socket.send(array, flags, copy=copy, track=track)


async def recv_numpy_array(socket: zmq.asyncio.Socket, has_topic=False, flags=0, copy=True, track=False) -> \
        Tuple[str, Mapping, numpy.ndarray]:
    """
    Receive a numpy array from a zmq socket
    :param socket: the zmq socket
    :param has_topic: indicates whether the message is prefixed with a topic (PUB / SUB)
    :param flags: see :meth `zmq.Socket.recv`
    :param copy: see :meth: `zmq.Socket.recv`
    :param track: see :meth: `zmq.Socket.recv`
    :return: tuple of topic (empty string if not applicable), additional arguments (may be empty)
     and received numpy array
    """
    try:
        if has_topic:
            topic = await socket.recv_string(flags=flags)
        else:
            topic = ''
        args_raw = await socket.recv(flags=flags)
        args = msgpack.unpackb(args_raw)
        md_raw = await socket.recv(flags=flags)
        md = msgpack.unpackb(md_raw)
        msg = await socket.recv(flags=flags, copy=copy, track=track)
        buf = memoryview(msg)
        array = numpy.frombuffer(buf, dtype=md['dtype'])
    except Exception as e:
        print('i was here ', e)  # 'utf-8' codec can't decode byte 0xe0 in position 5: invalid continuation byte
        return None, None, None

    return topic, args, array.reshape(md['shape'])


def recv_numpy_array_sync(socket: zmq.Socket, has_topic=False, flags=0, copy=True, track=False) -> \
        Tuple[str, Mapping, numpy.ndarray]:
    """
    Receive a numpy array from a zmq socket
    :param socket: the zmq socket
    :param has_topic: indicates whether the message is prefixed with a topic (PUB / SUB)
    :param flags: see :meth `zmq.Socket.recv`
    :param copy: see :meth: `zmq.Socket.recv`
    :param track: see :meth: `zmq.Socket.recv`
    :return: tuple of topic (empty string if not applicable), additional arguments (may be empty)
     and received numpy array
    """
    try:
        if has_topic:
            topic = socket.recv_string(flags=flags)
        else:
            topic = ''
        args_raw = socket.recv(flags=flags)
        args = msgpack.unpackb(args_raw)
        md_raw = socket.recv(flags=flags)
        md = msgpack.unpackb(md_raw)
        msg = socket.recv(flags=flags, copy=copy, track=track)
        buf = memoryview(msg)
        array = numpy.frombuffer(buf, dtype=md['dtype'])
    except Exception as e:
        print('i was here syn ', e)  # 'utf-8' codec can't decode byte 0xe0 in position 5: invalid continuation byte
        return None, None, None

    return topic, args, array.reshape(md['shape'])
