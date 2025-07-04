import logging
import sys

LOG_LEVEL_DEBUG = logging.DEBUG
LOG_LEVEL_INFO = logging.INFO
LOG_LEVEL_WARNING = logging.WARNING
LOG_LEVEL_ERROR = logging.ERROR
LOG_LEVEL_CRITICAL = logging.CRITICAL

def setup_logger(name: str = None, level: int = LOG_LEVEL_INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if name in (None, "", "root"):
        # Только для root-логгера добавляем handler
        if logger.hasHandlers():
            logger.handlers.clear()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        # Для дочерних логгеров propagate=True, handler не добавляем
        logger.propagate = True
    return logger
