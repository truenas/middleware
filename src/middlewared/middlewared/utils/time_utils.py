from datetime import datetime, UTC, timedelta

UTC_EPOCH = datetime.fromtimestamp(0, UTC)


def utc_now(naive: bool = True) -> datetime:
    """Wrapper for `datetime.now(UTC)`. Exclude timezone if `naive=True`."""
    dt = datetime.now(UTC)
    return dt.replace(tzinfo=None) if naive else dt


def datetime_to_epoch_days(value: datetime) -> int:
    """ Convert datetime to days since epoch. """
    if not isinstance(value, datetime):
        raise TypeError(f'{type(value)}: unexpected type')

    return (value - UTC_EPOCH).days


def epoch_days_to_datetime(value: int) -> datetime:
    """ Convert days since epoch into a UTC datetime object """
    if not isinstance(value, int):
        raise TypeError(f'{type(value)}: unexpected type')

    return UTC_EPOCH + timedelta(days=value)
