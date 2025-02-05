import logging
import os
import sys
import time
from functools import cached_property


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


def log_reentrant(message: str):
    current_time = time.time()
    seconds = int(current_time)
    milliseconds = int((current_time - seconds) * 1000)
    message = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(seconds)) + f",{milliseconds:03d} " + message
    if not message.endswith('\n'):
        message += '\n'
    os.write(sys.stderr.fileno(), message.encode())
