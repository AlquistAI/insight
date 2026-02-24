# -*- coding: utf-8 -*-
"""
    common.core
    ~~~~~~~~~~~

    Core component utilities (logging, etc.).
"""

import logging

_LOGGER: logging.Logger | None = None


def get_component_logger() -> logging.Logger:
    if _LOGGER is None:
        raise RuntimeError("Logger not initialized")
    return _LOGGER


def set_component_logger(logger: logging.Logger):
    global _LOGGER
    _LOGGER = logger
