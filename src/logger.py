import logging
import os

import aiologger

from .singleton import Singleton


__all__ = ('logger',)


class Logger(aiologger.Logger, metaclass=Singleton):
    pass


if os.name == 'nt':
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s'))
    logger.addHandler(handler)
else:
    logger = Logger.with_default_handlers()

logger.level = logging.DEBUG
