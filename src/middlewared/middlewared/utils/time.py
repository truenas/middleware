from datetime import datetime, UTC


def now(naive=True):
    return datetime.now(None if naive else UTC)
