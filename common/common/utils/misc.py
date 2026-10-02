# -*- coding: utf-8 -*-
"""
    common.utils.misc
    ~~~~~~~~~~~~~~~~~

    Miscellaneous/uncategorized utility functions used throughout the project.
"""

from typing import Any, Generator


def generate_batches(iterable, n: int = 1):
    for ndx in range(0, ln := len(iterable), n):
        yield iterable[ndx:min(ndx + n, ln)]


def yield_from_with_return(gen: Generator[Any, None, Any], on_return) -> Generator:
    """
    Yield all items of a generator and pass its return value to a callback.

    Plain iteration (`for`/`yield from` in a non-generator context) discards the generator's return
    value - this helper makes it available without having to catch `StopIteration` manually.

    :param gen: input generator
    :param on_return: callback called with the generator's return value once it is exhausted
    :return: generator yielding the items of the input generator
    """

    on_return(yield_ := (yield from gen))
    return yield_


def consume_generator(gen: Generator) -> tuple[list[Any], Any]:
    """
    Consume a generator and get both its items and its return value.

    :param gen: input generator
    :return: yielded items, generator return value
    """

    items = []

    while True:
        try:
            items.append(next(gen))
        except StopIteration as e:
            return items, e.value


def dict_to_dot_keys(inp: dict, prefix: str = "") -> dict:
    """Convert keys in a dict to dot notation."""

    out = {}

    for k, v in inp.items():
        if isinstance(v, dict):
            out.update(dict_to_dot_keys(v, prefix=f"{prefix}.{k}"))
        else:
            out[f"{prefix}.{k}"] = v

    return {k.lstrip("."): v for k, v in out.items()}
