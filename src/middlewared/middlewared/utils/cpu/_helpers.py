"""Low-level sysfs and parsing helpers shared across the cpu sub-package."""

import typing


def _read_int(path: str) -> int | None:
    """Read a single int from a sysfs file, returning None on missing or
    unparseable content."""
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError, OSError):
        return None


def _read_str(path: str) -> str | None:
    """Read a sysfs file as text, returning None on missing or unreadable."""
    try:
        with open(path) as f:
            return f.read().strip()
    except (FileNotFoundError, OSError):
        return None


def _parse_cpulist(s: str) -> list[int]:
    """Parse a Linux cpulist format string into the explicit list of CPU IDs.

    Supports comma-separated values, ranges (``"0-3"``), and combinations
    (``"0,2-3"``). Returns an empty list for empty input. Raises ``ValueError``
    on malformed tokens.
    """
    out: list[int] = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def _numeric(d: dict[str, typing.Any], key: str) -> float | None:
    """Return ``d[key]`` if it's a finite numeric reading, else None.

    Uses ``isinstance`` rather than truthiness so a legitimate ``0.0``
    sensor reading is preserved.
    """
    v = d.get(key)
    return float(v) if isinstance(v, (int, float)) else None
