import os
import syslog
import uuid

from middlewared.utils.time_utils import time_now


def syslog_message(message):
    data = f'<{syslog.LOG_USER | syslog.LOG_INFO}>'

    data += f'{time_now().strftime("%b %d %H:%M:%S")} '

    data += 'TNAUDIT_MIDDLEWARE: '

    data += message

    data = data.encode('ascii', 'ignore')

    return data
