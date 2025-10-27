import re

from croniter import croniter

CRON_FIELDS = ('minute', 'hour', 'dom', 'month', 'dow')


def croniter_for_schedule(schedule: dict, *args, **kwargs) -> croniter:
    """
    Create a croniter object from a schedule dictionary.

    :param schedule: Dictionary containing cron fields
    :param args: Additional positional arguments passed to croniter constructor
    :param kwargs: Additional keyword arguments passed to croniter constructor
    :return: Cron expression for the schedule
    :raises ValueError: If the schedule contains invalid cron expressions
    """
    cron_expression = ''
    for field in CRON_FIELDS:
        value = schedule.get(field) or '*'
        if '/' in value and not re.match(r'^(\*|[0-9]+-[0-9]+)/([0-9]+)$', value):
            raise ValueError('Only range or `*` are allowed before `/`')

        cron_expression += f'{value} '

    return croniter(cron_expression, *args, **kwargs)
