import re

_MAJOR_MINOR_RE = re.compile(r"[1-9][0-9]*\.[0-9]+")


def parse_version_string(version_string: str) -> str | None:
    """
    This util retrieves version numbers from version string i.e 25.04.0 or 25.1.1.1.
    If an invalid version string is specified, it will return null in that case.

    It is being used for determining release notes url for docs team and in TNC service for heartbeat.
    """
    to_format = version_string.split("-")[0].split(".")  # looks like ['23', '10', '0', '1']
    if len(to_format) < 2:
        return None

    return ".".join(to_format)


def parse_major_minor_version(raw: str | None) -> tuple[int, int] | None:
    """
    Strict "<major>.<minor>" parser: non-zero major (no leading zeros, any
    digit count), numeric minor. Returns (major, minor) or None.

    Everything else ("", "0100", "0.9", "01.0", "1", "1.0.0", "1.0-beta", ...)
    is rejected. Surrounding whitespace is tolerated.
    """
    if not raw:
        return None
    head = raw.strip()
    if not _MAJOR_MINOR_RE.fullmatch(head):
        return None
    major, minor = head.split(".")
    return (int(major), int(minor))
