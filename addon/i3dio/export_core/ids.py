# i3dio/export_core/ids.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from itertools import count


class IdKind(Enum):
    NODE = auto()
    SHAPE = auto()
    MATERIAL = auto()
    FILE = auto()


@dataclass(slots=True)
class IdAllocator:
    start: int = 1
    counters: dict[IdKind, object] = field(init=False)

    def __post_init__(self) -> None:
        self.counters = {k: count(self.start) for k in IdKind}

    def alloc(self, kind: IdKind) -> int:
        return next(self.counters[kind])
