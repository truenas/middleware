from datetime import datetime, UTC


def utc_now(naive=True):
    """Wrapper for `datetime.now(UTC)`. Exclude timezone if `naive=True`."""
    dt = datetime.now(UTC)
    return dt.replace(tzinfo=None) if naive else dt
