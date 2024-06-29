import itertools
import math
import os
import sys
from collections import UserDict
from enum import Enum
from typing import Any, Callable, Iterable, Optional, TypeVar

# Various utils.

T = TypeVar("T")

int_inf = sys.maxsize
neg_int_inf = -sys.maxsize - 1


def raiseException(text: str):
    eprint(text)
    raise Exception()


def eprint(*args: Any, **kwargs: Any):
    print(*args, file=sys.stderr, **kwargs)


def flatten(list_of_lists: Iterable[Iterable[Any]]):
    return list(itertools.chain.from_iterable(list_of_lists))


def get_first_list_item_or_none(list: list[Any]):
    if len(list) > 0:
        return list[0]
    else:
        return None


def remove_first_item_from_list_matching_condition(
        list: list[Any], condition: Callable[[Any], bool]
) -> None:
    for i, item in enumerate(list):
        if condition(item):
            list.pop(i)
            break


def get_first_list_item_matching_condition(
        list: list[T], condition: Callable[[T], bool]
) -> T | None:
    for item in list:
        if condition(item):
            return item


def not_none(obj: Optional[T]) -> T:
    assert obj is not None
    return obj


def clamp_int(value: int, min_lim: int, max_lim: int) -> int:
    return max(min_lim, min(value, max_lim))


def clamp_float(value: float, min_lim: int | float, max_lim: int | float) -> float:
    return max(min_lim, min(value, max_lim))


def open_with_create_missing_directories(filepath: str, mode: str, *args, **kwargs):
    """
    Opens a file and returns a stream. Creates missing directories if needed.

    Refer to `open()` docs.

    :param filepath: Path to file.
    :param mode: Mode. Refer to `open()` docs.
    :param args: Args to passthrough to `open()`. Refer to `open()` docs.
    :param kwargs: Args to passthrough to `open()`. Refer to `open()` docs.
    :return: Filestream.
    """

    dir_path = os.path.split(os.path.abspath(filepath))[0]
    os.makedirs(dir_path, exist_ok=True)
    return open(filepath, mode, *args, **kwargs)
