import logging
import os
import sys
import time
from functools import cached_property
from contextlib import contextmanager
from collections.abc import Iterator


class LoggerMixin:
    _DEFAULT_ARGS = {'format': '%(asctime)s %(levelname)-7s %(name)s | %(message)s'}

    def __init__(self, *args, logger_name='', **kwargs):
        super().__init__(*args, **kwargs)
        self._logger_name = logger_name

    @classmethod
    def configure_logger(cls, **kwargs):
        for arg in cls._DEFAULT_ARGS:
            if arg not in kwargs:
                kwargs[arg] = cls._DEFAULT_ARGS[arg]

        try:
            logging.basicConfig(**kwargs)
        except ValueError:
            logging.basicConfig(level=logging.WARNING)
            logging.warning('Unknown log level {}, set to WARNING'.format(kwargs['level']))

    @cached_property
    def logger(self) -> logging.Logger:
        if len(self._logger_name):
            name = self._logger_name
        else:
            name = self.__class__.__name__
        return logging.getLogger(name)

    @classmethod
    def static_logger(cls) -> logging.Logger:
        name = cls.__name__
        return logging.getLogger(name)

    @contextmanager
    def time_it(self, prefix: str, limit_ms: float, log_severity=logging.WARNING) -> Iterator[None]:
        """
        Context manager for measuring the execution time of a block of code and logging it
        if it exceeds a specified time limit. This can help in identifying performance
        bottlenecks by monitoring the duration of operations.
        Very low overhead.

        :param prefix: A string used as a message prefix when logging the duration.
        :param limit_ms: A float representing the maximum allowed duration in milliseconds.
        :param log_severity: Logging severity level from the ``logging`` module to use when
            the log message is emitted. Defaults to ``logging.WARNING``.
        :return: Yields control back to the caller allowing the execution of a code block
            within the context.
        """
        tic: int = time.perf_counter_ns()
        try:
            yield
        finally:
            toc: int = time.perf_counter_ns()
            if toc - tic > limit_ms * 1e6:
                self.logger.log(log_severity, f"%s took = %.3f ms", prefix, (toc - tic) / 1e6)


def log_reentrant(message: str):
    current_time = time.time()
    seconds = int(current_time)
    milliseconds = int((current_time - seconds) * 1000)
    message = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(seconds)) + f",{milliseconds:03d} " + message
    if not message.endswith('\n'):
        message += '\n'
    os.write(sys.stderr.fileno(), message.encode())
