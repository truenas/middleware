from datetime import datetime, UTC


def time_now(naive=True):
    """Wrapper for `datetime.now()`. Exclude timezone if `naive=True`."""
    return datetime.now(None if naive else UTC)
