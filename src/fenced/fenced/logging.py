# Copyright (c) 2019 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import logging
import logging.config
import logging.handlers

LOG_FILE = '/var/log/fenced.log'

class FaultSysLogHandler(logging.handlers.SysLogHandler):
    """
    If for some reason syslogd is not running we do not want tracebacks.
    """
    def emit(self, *args, **kwargs):
        try:
            super().emit(*args, **kwargs)
        except Exception:
            pass

    def handleError(self, record):
        if self.sock:
            self.sock.close()
            self.sock = None


def setup_logging(foreground):
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'simple': {
                'format': '[%(asctime)s - %(name)s:%(lineno)s] %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'syslog': {
                'class': 'fenced.logging.FaultSysLogHandler',
                'address': '/var/run/log',
                'formatter': 'simple',
                'level': 'INFO',
                'facility': 'daemon',
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'simple',
                'level': 'INFO',
                'filename': LOG_FILE,
                'maxBytes': 1000000, # 1MB size
                'backupCount': '3',
            },
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'simple',
                'level': 'DEBUG' if foreground else 'INFO',
                'stream': 'ext://sys.stdout',
            },
        },
        'loggers': {
            '': {
                'handlers': ['console', 'syslog', 'file'],
                'level': 'DEBUG',
                'propagate': True,
            },
        },
    })

