# -*- coding=utf-8 -*-
from croniter import croniter

CRON_FIELDS = ["minute", "hour", "dom", "month", "dow"]


def croniter_for_schedule(schedule, *args, **kwargs):
    cron_expression = ''
    for field in CRON_FIELDS:
        cron_expression += schedule.get(field) + ' ' if schedule.get(field) else '* '

    return croniter(cron_expression, *args, **kwargs)
