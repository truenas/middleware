# -*- coding=utf-8 -*-
import re

from croniter import croniter


DB_FIELDS =   ('minute', 'hour', 'daymonth', 'month', 'dayweek')
CRON_FIELDS = ('minute', 'hour', 'dom',      'month', 'dow')


def croniter_for_schedule(schedule: dict, *args, **kwargs) -> croniter:
    """
    Create a croniter object from a schedule dictionary.
    
    :param schedule: Dictionary containing cron fields
    :param args: Additional positional arguments passed to croniter constructor
    :param kwargs: Additional keyword arguments passed to croniter constructor
    :return: Configured croniter object for the schedule
    :raises ValueError: If the schedule contains invalid cron expressions
    """
    cron_expression = ''
    for field in CRON_FIELDS:
        value = schedule.get(field) or '*'
        if '/' in value and not re.match(r'^(\*|[0-9]+-[0-9]+)/([0-9]+)$', value):
            raise ValueError('Only range or `*` are allowed before `/`')

        cron_expression += f'{value} '

    return croniter(cron_expression, *args, **kwargs)


def convert_schedule_to_db_format(data_dict: dict, schedule_name='schedule', key_prefix='', begin_end=False) -> None:
    """
    Convert a schedule dictionary to database field format.
    
    Transforms cron field names to database field names and flattens the schedule into individual fields.
    
    :param data_dict: Dictionary to modify in-place
    :param schedule_name: Key name containing the schedule dictionary to convert
    :param key_prefix: Prefix to add to database field names
    :param begin_end: Whether to also convert 'begin' and 'end' time fields
    """
    if schedule_name not in data_dict:
        return

    schedule = data_dict.pop(schedule_name)
    db_fields, cron_fields = DB_FIELDS, CRON_FIELDS
    if begin_end:
        db_fields += ('begin', 'end')
        cron_fields += ('begin', 'end')

    if schedule is None:
        data_dict.update((key_prefix + field, None) for field in db_fields)
    else:
        data_dict.update(
            (key_prefix + db_field, schedule[cron_field])
            for db_field, cron_field in zip(db_fields, cron_fields)
            if cron_field in schedule
        )


def convert_db_format_to_schedule(data_dict: dict, schedule_name='schedule', key_prefix='', begin_end=False) -> None:
    """
    Convert database field format to a schedule dictionary.
    
    Transforms database field names to cron field names and creates a nested schedule dictionary.
    
    :param data_dict: Dictionary to modify in-place
    :param schedule_name: Key name for the created schedule dictionary
    :param key_prefix: Prefix to look for on database field names
    :param begin_end: Whether to also convert 'begin' and 'end' time fields
    """
    data_dict[schedule_name] = {}

    def add_field_to_schedule(db_field: str, cron_field: str | None = None, transform=lambda x: x):
        key = key_prefix + db_field
        if key in data_dict:
            value = data_dict.pop(key)
            if value is None:
                data_dict[schedule_name] = None
            elif (schedule := data_dict[schedule_name]) is not None:
                schedule[cron_field or db_field] = transform(value)

    for db_field, cron_field in zip(DB_FIELDS, CRON_FIELDS):
        add_field_to_schedule(db_field, cron_field)

    if not begin_end:
        return

    for field in ('begin', 'end'):
        add_field_to_schedule(field, transform=lambda x: str(x)[:5])
