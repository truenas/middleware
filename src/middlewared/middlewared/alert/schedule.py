from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from dateutil.tz import tzlocal


class BaseSchedule(ABC):
    @abstractmethod
    def should_run(self, now: datetime, last_run: datetime) -> bool:
        ...


class IntervalSchedule(BaseSchedule):
    def __init__(self, interval: timedelta):
        self.interval = interval

    def should_run(self, now: datetime, last_run: datetime) -> bool:
        return now >= last_run + self.interval


class CrontabSchedule(BaseSchedule):
    def __init__(self, hour: int):
        self.hour = hour

    def should_run(self, now: datetime, last_run: datetime) -> bool:
        if last_run == datetime.min:
            return True

        local_now = now + tzlocal().utcoffset(now)  # type: ignore[operator]
        local_last_run = last_run + tzlocal().utcoffset(last_run)  # type: ignore[operator]
        return local_now.hour == self.hour and local_last_run.date() != local_now.date()
