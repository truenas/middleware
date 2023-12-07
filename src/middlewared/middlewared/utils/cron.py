# -*- coding=utf-8 -*-
import re

from croniter import croniter

CRON_FIELDS = ["minute", "hour", "dom", "month", "dow"]


def croniter_for_schedule(schedule, *args, **kwargs):
    cron_expression = ''
    for field in CRON_FIELDS:
        value = schedule.get(field) or '*'
        if '/' in value and not re.match(r'^(\*|[0-9]+-[0-9]+)/([0-9]+)$', value):
            raise ValueError("Only range or `*` are allowed before `/`")

        cron_expression += f'{value} '

    return croniter(cron_expression, *args, **kwargs)
