from functools import cache
import os

ZONEINFO_DIR = "/usr/share/zoneinfo"
FALLBACK_TZ = "UTC"

__all__ = ("tz_choices", "timezone_is_available", "effective_timezone")


@cache
def _available_zones() -> frozenset[str]:
    # Walk /usr/share/zoneinfo once and collect every name that resolves to a
    # real file (regular file or non-dangling symlink). Building a set up-front
    # lets the validator and dropdown do O(1) membership checks against ~600
    # candidates from tzdata.zi instead of one stat() per candidate. Cached for
    # the lifetime of the process; if the admin installs `tzdata-legacy`,
    # restart middlewared to refresh.
    found: set[str] = set()
    pending: list[str] = [""]
    while pending:
        rel = pending.pop()
        path = os.path.join(ZONEINFO_DIR, rel) if rel else ZONEINFO_DIR
        with os.scandir(path) as it:
            for entry in it:
                name = f"{rel}/{entry.name}" if rel else entry.name
                if entry.is_dir(follow_symlinks=False):
                    pending.append(name)
                elif entry.is_file(follow_symlinks=True):
                    # is_file(follow_symlinks=True) is False for dangling
                    # symlinks because the underlying stat() fails -- exactly
                    # the filter we want.
                    found.add(name)
    return frozenset(found)


def timezone_is_available(name: str) -> bool:
    return bool(name) and name in _available_zones()


def effective_timezone(name: str) -> str:
    # Used at runtime by consumers (zettarepl scheduler, TZ env var, ...) so
    # that a stale DB value left over from an upgrade -- e.g. "Japan" without
    # tzdata-legacy installed -- cannot crash them. The user-visible alert is
    # raised exactly once, by the localtime etc renderer.
    return name if timezone_is_available(name) else FALLBACK_TZ


@cache
def tz_choices() -> tuple[tuple[str, str], ...]:
    # Logic deduced from what timedatectl list-timezones does, with an
    # additional on-disk existence check: tzdata.zi declares all historical
    # aliases (e.g. "Japan", "GB", "Hongkong"), but on Debian trixie those
    # symlinks ship in `tzdata-legacy` which is not installed by default. Keep
    # only entries whose zone file actually resolves so we never offer the user
    # a name that would produce a dangling /etc/localtime.
    available = _available_zones()
    tz: list[tuple[str, str]] = []
    with open(os.path.join(ZONEINFO_DIR, "tzdata.zi")) as f:
        for line in filter(lambda x: x and x[0] in ("Z", "L"), f):
            index = 1 if line[0] == "Z" else 2
            name = line.split()[index].strip()
            if name in available:
                tz.append((name, name))
    return tuple(tz)
