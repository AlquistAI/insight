# -*- coding: utf-8 -*-
"""
    common.utils.singleton
    ~~~~~~~~~~~~~~~~~~~~~~

    Singleton pattern that is used to instantiate a class only once per module.
"""

from abc import ABCMeta
from threading import Lock

LOCK = Lock()


class Singleton(type):
    """
    Singleton metaclass definition.

    The singleton identity depends on the parameters used in __init__.
    Uses thread lock via metaclass pattern.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """(Create and) call the one and only class instance."""

        key = (cls, args, str(kwargs))

        if key not in cls._instances:
            with LOCK:
                if key not in cls._instances:
                    cls._instances[key] = super(Singleton, cls).__call__(*args, **kwargs)

        return cls._instances[key]


class SingletonABC(ABCMeta, Singleton):
    """
    Singleton metaclass definition for abstract classes.

    The singleton identity depends on the parameters used in __init__.
    Uses thread lock via metaclass pattern.
    """

    pass
