from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class IdKind(Enum):
    NODE = auto()
    SHAPE = auto()
    MATERIAL = auto()
    FILE = auto()


@dataclass(slots=True)
class IdAllocator:
    next_id: dict[IdKind, int] = field(
        default_factory=lambda: {
            IdKind.NODE: 1,
            IdKind.SHAPE: 1,
            IdKind.MATERIAL: 1,
            IdKind.FILE: 1,
        }
    )

    def alloc(self, kind: IdKind) -> int:
        v = self.next_id[kind]
        self.next_id[kind] = v + 1
        return v
