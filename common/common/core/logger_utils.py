# -*- coding: utf-8 -*-
"""
    common.core.logger_utils
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Logging utilities.
"""

import functools
import logging
import time

from common.core import get_component_logger

logger = get_component_logger()


def log_elapsed_time(_func=None, *, level: int = logging.DEBUG, msg: str | None = None):
    """
    Log elapsed time of a function.

    Pattern: https://realpython.com/primer-on-python-decorators/#both-please-but-never-mind-the-bread

    :param _func: decorated function
    :param level: logging level of this time log
    :param msg: custom message
    :return: function decorator
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            message = msg or f"Function: {fn.__name__} in module: {fn.__module__}, elapsed time: {{elapsed_time}}"
            if "{elapsed_time}" not in message:
                message = f"{message}, elapsed time: {{elapsed_time}}"

            start = time.perf_counter()
            result = fn(*args, **kwargs)
            msg_fmt = {
                "elapsed_time": int(1000 * (time.perf_counter() - start)),
                "func_name_override": fn.__name__,
                "module_override": fn.__module__,
            }

            logger.log(level, message.format(**msg_fmt), extra=msg_fmt)
            return result

        return wrapper

    return decorator if _func is None else decorator(_func)
