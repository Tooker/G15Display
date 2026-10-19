"""G15 v1 special-key input report 2 (nine bytes, including report ID).

Bit positions are documented by libg15's processKeyEvent9Byte:
https://github.com/vividnightmare/libg15/blob/master/libg15.c
"""

from dataclasses import dataclass


# name, byte index, bit mask. The G15 v1 wiring is not a linear bit field.
KEY_BITS = (
    ("G1", 1, 0x01), ("G2", 2, 0x02), ("G3", 3, 0x04),
    ("G4", 4, 0x08), ("G5", 5, 0x10), ("G6", 6, 0x20),
    ("G7", 2, 0x01), ("G8", 3, 0x02), ("G9", 4, 0x04),
    ("G10", 5, 0x08), ("G11", 6, 0x10), ("G12", 7, 0x20),
    ("G13", 1, 0x04), ("G14", 2, 0x08), ("G15", 3, 0x10),
    ("G16", 4, 0x20), ("G17", 5, 0x40), ("G18", 8, 0x40),
    ("M1", 6, 0x01), ("M2", 7, 0x02), ("M3", 8, 0x04),
    ("MR", 7, 0x40),
    ("L1", 8, 0x80), ("L2", 2, 0x80), ("L3", 3, 0x80),
    ("L4", 4, 0x80), ("L5", 5, 0x80), ("LIGHT", 1, 0x80),
)


def decode_keys(report: bytes) -> frozenset[str] | None:
    """None means unrelated/malformed data; an empty set means all released."""
    if len(report) != 9 or report[0] != 2:
        return None
    return frozenset(name for name, offset, mask in KEY_BITS if report[offset] & mask)


@dataclass(frozen=True)
class KeyEvent:
    name: str
    pressed: bool


class KeyTracker:
    """Convert complete snapshots to edges; ignore duplicate/unrelated reports."""

    def __init__(self):
        self.held: frozenset[str] = frozenset()

    def update(self, report: bytes) -> list[KeyEvent]:
        current = decode_keys(report)
        if current is None:
            return []
        # Releases first, stable physical-key order within each group.
        events = [KeyEvent(name, False) for name, _, _ in KEY_BITS
                  if name in self.held and name not in current]
        events += [KeyEvent(name, True) for name, _, _ in KEY_BITS
                   if name in current and name not in self.held]
        self.held = current
        return events
