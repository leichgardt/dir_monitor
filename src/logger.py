import logging
import os

import aiologger

from src.singleton import Singleton


__all__ = ('logger',)


class Logger(aiologger.Logger, metaclass=Singleton):
    pass


if os.name == 'nt':  # windows
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s'))
    logger.addHandler(handler)
else:  # posix
    logger = Logger.with_default_handlers()

logger.level = logging.DEBUG
