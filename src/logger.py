import aiologger

from .singleton import Singleton


class Logger(aiologger.Logger, metaclass=Singleton):
    pass
