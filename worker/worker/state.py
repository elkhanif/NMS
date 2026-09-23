"""In-process hysteresis counters for the alert engine.

Kept in memory (not the database) since these are just "how many consecutive polls
have breached/recovered" counters used to decide when to flip an alert -- losing them
on a worker restart just means a slightly slower re-trigger, never incorrect data.
"""

from collections import defaultdict
from typing import Hashable

_breach_counts: dict[Hashable, int] = defaultdict(int)
_ok_counts: dict[Hashable, int] = defaultdict(int)


def record_breach(key: Hashable) -> int:
    _ok_counts[key] = 0
    _breach_counts[key] += 1
    return _breach_counts[key]


def record_ok(key: Hashable) -> int:
    _breach_counts[key] = 0
    _ok_counts[key] += 1
    return _ok_counts[key]


def reset(key: Hashable) -> None:
    _breach_counts[key] = 0
    _ok_counts[key] = 0
