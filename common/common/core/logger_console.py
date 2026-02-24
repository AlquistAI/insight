# -*- coding: utf-8 -*-
"""
    common.core.logger_console
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Console logging utilities.
"""

import logging
import sys

from common.core import middleware

DEFAULT_LOG_FORMAT = "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
HANDLER_NAME = "h_console"


class ContextFilter(logging.Filter):
    """
    Context filter injects contextual information into the application log.

    The response log is handled by `uvicorn.access` logger therefore context filter is not required.
    Headers and response information are in `uvicorn.access` scope variable.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if ctx := middleware.get_context():
            record.__dict__.update(ctx)
        return True


class HealthCheckFilter(logging.Filter):
    """Health check filter removes the health check call logs."""

    def filter(self, record: logging.LogRecord) -> bool:

        if isinstance(record.args, dict):
            return True

        try:
            return not (record.args and len(record.args) >= 3 and record.args[2] == "/health")
        except Exception as e:
            logging.error("Failed to parse record args: %s", e)

        return True


def setup(logger_name: str, log_level: str | int = logging.DEBUG, fmt: logging.Formatter | None = None):
    """
    Setup logging into console with defined name.

    We need to get logger by logger_name otherwise the context will not be in logstash.
    We cannot use logging.[debug|info|...] otherwise the logs will be duplicated in the docker with a different format.
    """

    logger_ = logging.getLogger(logger_name)

    # set up logging handler
    handler = logging.StreamHandler(sys.stdout)
    handler.name = HANDLER_NAME
    handler.setFormatter(fmt or logging.Formatter(DEFAULT_LOG_FORMAT))
    handler.setLevel(log_level)
    logger_.addHandler(handler)

    # set up filters
    logger_.addFilter(ContextFilter())
    logger_.addFilter(HealthCheckFilter())

    # set logging level
    logger_.setLevel(log_level)
    logging.getLogger("uvicorn.access").setLevel(logging.ERROR)

    logger_.info("Logger %s setup finished for console", logger_name)
    return logger_
