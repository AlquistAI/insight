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


def log_elapsed_time_stream(_func=None, *, level: int = logging.DEBUG, msg: str | None = None):
    """
    Log elapsed time of a generator function, incl. the time it took to yield the first item.

    `log_elapsed_time` cannot be used for a generator function - calling one only creates the generator object
    (instant), so the whole work happens after the elapsed time is logged. Here the timing spans the consumption of
    the generator, which also makes the time to the first yielded item available (the relevant latency for a streamed
    LLM response). The generator's return value is preserved, so it can still be used to report the token usage.

    :param _func: decorated generator function
    :param level: logging level of this time log
    :param msg: custom message
    :return: generator function decorator
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            message = msg or (
                f"Function: {fn.__name__} in module: {fn.__module__}, "
                "time to first item: {elapsed_first}, elapsed time: {elapsed_time}"
            )

            if "{elapsed_first}" not in message:
                message = f"{message}, time to first item: {{elapsed_first}}"

            if "{elapsed_time}" not in message:
                message = f"{message}, elapsed time: {{elapsed_time}}"

            gen = fn(*args, **kwargs)
            elapsed_first = None
            start = time.perf_counter()

            try:
                # Iterate manually - plain iteration would discard the generator's return value.
                while True:
                    try:
                        item = next(gen)
                    except StopIteration as stop:
                        return stop.value

                    if elapsed_first is None:
                        elapsed_first = int(1000 * (time.perf_counter() - start))

                    yield item

            finally:
                # Logged in `finally` to report the timing even if the consumer abandons the generator.
                msg_fmt = {
                    "elapsed_first": elapsed_first,
                    "elapsed_time": int(1000 * (time.perf_counter() - start)),
                    "func_name_override": fn.__name__,
                    "module_override": fn.__module__,
                }

                logger.log(level, message.format(**msg_fmt), extra=msg_fmt)

        return wrapper

    return decorator if _func is None else decorator(_func)
