import asyncio
from typing import Dict, Iterable, Tuple, Awaitable, TypeVar, Hashable, Generator

from vif.logger.logger import LoggerMixin

T = TypeVar('T', bound=Hashable)
R = TypeVar('R')
C = Awaitable[R]


async def gather_map(key_to_coro: Iterable[Tuple[T, C]]) -> Dict[T, R]:
    async def _map_to_key(k, coro):
        return k, await coro

    res = await asyncio.gather(*(_map_to_key(k, v) for k, v in key_to_coro))
    return dict(res)


def tick_generator(period_s: float, drop_missed=False, time_source=None) -> Generator[float, None, None]:
    """
    generate periodic sleep times without drift
    use in async like:
        g = tick_generator(2)
        while True:
            # do stuff
            await asyncio.sleep(next(g))
    also works for sync version by using:
        g = tick_generator(2, drop_missed=True, time_source=time.time)
        exit_event = threading.Event()
        while not exit_event.is_set():
            # do stuff
            exit_event.wait(next(g))

    abort with g.throw(StopIteration)  --> use to abort waiting
    or
    close with g.close()  --> use when not waiting anymore

    :param period_s: wanted periodic delay in seconds
    :param drop_missed: when True, drop ticks when checked too late. Otherwise immediately return multiple times 0.
    :param time_source: default uses async loop timer, or for sync use eg: time.time
    :return: generator for periodic timing tasks
    """
    if time_source is None:
        loop = asyncio.get_event_loop()
        time_func = loop.time
    else:
        time_func = time_source
    t_start = time_func()
    count = 0
    try:
        while True:
            count += 1
            t_now = time_func()
            wait_time = max(t_start + count * period_s - t_now, 0)
            # fast-forward count if we missed a period and should drop ticks
            if drop_missed and wait_time == 0:
                count = int((t_now - t_start) / period_s)
            yield wait_time
    except StopIteration:
        pass


class DatagramProtocol(LoggerMixin, asyncio.DatagramProtocol):

    def __init__(self):
        super().__init__()
        # makeshift construct since asyncio does not provide a dequeue
        # we use _q_front to emulate the q.push_front of a dequeue (needed since we receive packages
        # of arbitrary length)
        self._q_front: bytes = b''  # buffer containing some bytes to be consumed before accessing the queue
        self._q: asyncio.Queue[bytes] = asyncio.Queue()  # queue containing bytes of any length (except zero)

    def datagram_received(self, data: bytes, addr):
        self._q.put_nowait(data)

    async def get_n(self, n: int) -> bytes:
        """
        Get the first n bytes received
        :param n: number of bytes
        :return: n bytes
        """

        # take from front
        data_front = self._q_front[:n]
        self._q_front = self._q_front[n:]

        if len(data_front) == n:
            # we have all we need
            return data_front

        # reduce by number of data already taken
        n -= len(data_front)

        # front is exhausted, receive new data
        self._q_front = await self._q.get()
        return data_front + await self.get_n(n)
