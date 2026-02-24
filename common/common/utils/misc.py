# -*- coding: utf-8 -*-
"""
    common.utils.misc
    ~~~~~~~~~~~~~~~~~

    Miscellaneous/uncategorized utility functions used throughout the project.
"""


def generate_batches(iterable, n: int = 1):
    for ndx in range(0, ln := len(iterable), n):
        yield iterable[ndx:min(ndx + n, ln)]


def dict_to_dot_keys(inp: dict, prefix: str = "") -> dict:
    """Convert keys in a dict to dot notation."""

    out = {}

    for k, v in inp.items():
        if isinstance(v, dict):
            out.update(dict_to_dot_keys(v, prefix=f"{prefix}.{k}"))
        else:
            out[f"{prefix}.{k}"] = v

    return {k.lstrip("."): v for k, v in out.items()}
