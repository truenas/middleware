from datetime import datetime
import os
import syslog
import uuid


def syslog_message(message):
    data = f'<{syslog.LOG_USER | syslog.LOG_INFO}>'

    data += f'{datetime.now(datetime.UTC).strftime("%b %d %H:%M:%S")} '

    data += 'TNAUDIT_MIDDLEWARE: '

    data += message

    data = data.encode('ascii', 'ignore')

    return data
