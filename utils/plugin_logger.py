from nonebot import logger as _logger


class PrefixedLogger:

    def __init__(self, name: str):
        self._name = name
        self._log = _logger.opt(depth=1)

    def _fmt(self, msg):
        return f"[{self._name}] {msg}"

    def debug(self, msg, *args, **kwargs):
        self._log.debug(self._fmt(msg))

    def info(self, msg, *args, **kwargs):
        self._log.info(self._fmt(msg))

    def warning(self, msg, *args, **kwargs):
        self._log.warning(self._fmt(msg))

    warn = warning

    def error(self, msg, *args, **kwargs):
        self._log.error(self._fmt(msg))

    def critical(self, msg, *args, **kwargs):
        self._log.critical(self._fmt(msg))

    def exception(self, msg, *args, **kwargs):
        _logger.opt(depth=1, exception=True).error(self._fmt(msg))

    def setLevel(self, level):
        return None

    def addHandler(self, handler):
        return None

    @property
    def handlers(self):
        return [None]


def get_logger(name: str) -> PrefixedLogger:
    return PrefixedLogger(name)
