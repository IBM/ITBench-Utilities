import logging
from typing import Union, Literal
from itbench_utilities.app.config import PROJECT_LOG_LEVEL, ROOT_LOG_LEVEL

log_format = "[%(asctime)s %(levelname)s %(name)s] %(message)s"


def to_log_level(level: Union[str, int]):
    if isinstance(level, int):
        return level
    if not isinstance(level, str):
        return logging.INFO
    x = level.lower()
    if x == "info":
        return logging.INFO
    elif x == "warn" or x == "warning":
        return logging.WARNING
    elif x == "error":
        return logging.ERROR
    elif x == "debug":
        return logging.DEBUG
    elif x == "fatal":
        return logging.FATAL
    elif x == "notset" or x == "none":
        return logging.NOTSET
    else:
        return logging.INFO


def init(project_log_level: Union[str, int] = PROJECT_LOG_LEVEL):
    root_log_level = to_log_level(ROOT_LOG_LEVEL)
    logging.basicConfig(format=log_format, level=root_log_level)
    project_log_level = to_log_level(project_log_level)
    logger = logging.getLogger("itbench_utilities")
    logger.setLevel(project_log_level)
