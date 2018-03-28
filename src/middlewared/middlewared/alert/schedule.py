from datetime import datetime
from dateutil.tz import tzlocal


class BaseSchedule:
    def should_run(self, now, last_run):
        raise NotImplementedError


class IntervalSchedule:
    def __init__(self, interval):
        self.interval = interval

    def should_run(self, now, last_run):
        return now >= last_run + self.interval


class CrontabSchedule:
    def __init__(self, hour):
        self.hour = hour

    def should_run(self, now, last_run):
        if last_run == datetime.min:
            return True

        local_now = now + tzlocal().utcoffset(now)
        local_last_run = last_run + tzlocal().utcoffset(last_run)
        return local_now.hour == self.hour and local_last_run.date() != local_now.date()
