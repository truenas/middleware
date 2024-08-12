from datetime import datetime, UTC


def time_now(naive=True):
    return datetime.now(None if naive else UTC)
