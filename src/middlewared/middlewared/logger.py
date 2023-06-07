import logging
from logging.config import dictConfig
import logging.handlers
import os
import sys

from .utils import sw_version, sw_version_is_stable


# markdown debug is also considered useless
logging.getLogger('MARKDOWN').setLevel(logging.INFO)
# asyncio runs in debug mode but we do not need INFO/DEBUG
logging.getLogger('asyncio').setLevel(logging.WARN)
# We dont need internal aiohttp debug logging
logging.getLogger('aiohttp.internal').setLevel(logging.WARN)
# We dont need internal botocore debug logging
logging.getLogger('botocore').setLevel(logging.WARN)
# we dont need ws4py close debug messages
logging.getLogger('ws4py').setLevel(logging.WARN)
# we dont need GitPython debug messages (used in iocage)
logging.getLogger('git.cmd').setLevel(logging.WARN)
# issues garbage warnings
logging.getLogger('googleapiclient').setLevel(logging.ERROR)
# registered 'pbkdf2_sha256' handler: <class 'passlib.handlers.pbkdf2.pbkdf2_sha256'>
logging.getLogger('passlib.registry').setLevel(logging.INFO)

LOGFILE = '/var/log/middlewared.log'
ZETTAREPL_LOGFILE = '/var/log/zettarepl.log'
FAILOVER_LOGFILE = '/root/syslog/failover.log'
logging.TRACE = 6


def trace(self, message, *args, **kws):
    if self.isEnabledFor(logging.TRACE):
        self._log(logging.TRACE, message, args, **kws)


logging.addLevelName(logging.TRACE, "TRACE")
logging.Logger.trace = trace


class LoggerFormatter(logging.Formatter):
    """Format the console log messages"""

    CONSOLE_COLOR_FORMATTER = {
        'YELLOW': '\033[1;33m',  # (warning)
        'GREEN': '\033[1;32m',  # (info)
        'RED': '\033[1;31m',  # (error)
        'HIGHRED': '\033[1;41m',  # (critical)
        'RESET': '\033[1;m',  # Reset
    }
    LOGGING_LEVEL = {
        'CRITICAL': 50,
        'ERROR': 40,
        'WARNING': 30,
        'INFO': 20,
        'DEBUG': 10,
        'NOTSET': 0
    }

    def format(self, record):
        """Set the color based on the log level.

            Returns:
                logging.Formatter class.
        """

        if record.levelno == self.LOGGING_LEVEL['CRITICAL']:
            color_start = self.CONSOLE_COLOR_FORMATTER['HIGHRED']
        elif record.levelno == self.LOGGING_LEVEL['ERROR']:
            color_start = self.CONSOLE_COLOR_FORMATTER['HIGHRED']
        elif record.levelno == self.LOGGING_LEVEL['WARNING']:
            color_start = self.CONSOLE_COLOR_FORMATTER['RED']
        elif record.levelno == self.LOGGING_LEVEL['INFO']:
            color_start = self.CONSOLE_COLOR_FORMATTER['GREEN']
        elif record.levelno == self.LOGGING_LEVEL['DEBUG']:
            color_start = self.CONSOLE_COLOR_FORMATTER['YELLOW']
        else:
            color_start = self.CONSOLE_COLOR_FORMATTER['RESET']

        color_reset = self.CONSOLE_COLOR_FORMATTER['RESET']

        record.levelname = color_start + record.levelname + color_reset

        return logging.Formatter.format(self, record)


class LoggerStream(object):

    def __init__(self, logger):
        self.logger = logger
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.debug(line.rstrip())


class ErrorProneRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def handleError(self, record):
        try:
            super().handleError(record)
        except ValueError:
            # sys.stderr can be closed by core.reconfigure_logging which leads to
            # ValueError: I/O operation on closed file. raised on every operation that
            # involves logging
            pass

    def doRollover(self):
        super().doRollover()
        # We must reconfigure stderr/stdout streams after rollover
        reconfigure_logging()


class Logger(object):
    """Pseudo-Class for Logger - Wrapper for logging module"""
    def __init__(
        self, application_name, debug_level=None,
        log_format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s():%(lineno)d - %(message)s'
    ):
        self.application_name = application_name
        self.debug_level = debug_level or 'DEBUG'
        self.log_format = log_format

        self.DEFAULT_LOGGING = {
            'version': 1,
            'disable_existing_loggers': False,
            'loggers': {
                '': {
                    'level': 'NOTSET',
                    'handlers': ['file'],
                },
                'zettarepl': {
                    'level': 'NOTSET',
                    'handlers': ['zettarepl_file'],
                    'propagate': False,
                },
                'failover': {
                    'level': 'NOTSET',
                    'handlers': ['failover_file', 'sys-logger'],
                    'propagate': False,
                },
            },
            'handlers': {
                'sys-logger': {
                    'level': 'DEBUG',
                    'class': 'logging.handlers.SysLogHandler',
                    'address': '/var/run/log',
                    'formatter': 'file',
                },
                'file': {
                    'level': 'DEBUG',
                    'class': 'middlewared.logger.ErrorProneRotatingFileHandler',
                    'filename': LOGFILE,
                    'mode': 'a',
                    'maxBytes': 10485760,
                    'backupCount': 5,
                    'encoding': 'utf-8',
                    'formatter': 'file',
                },
                'zettarepl_file': {
                    'level': 'DEBUG',
                    'class': 'middlewared.logger.ErrorProneRotatingFileHandler',
                    'filename': ZETTAREPL_LOGFILE,
                    'mode': 'a',
                    'maxBytes': 10485760,
                    'backupCount': 5,
                    'encoding': 'utf-8',
                    'formatter': 'zettarepl_file',
                },
                'failover_file': {
                    'level': 'DEBUG',
                    'class': 'middlewared.logger.ErrorProneRotatingFileHandler',
                    'filename': FAILOVER_LOGFILE,
                    'mode': 'a',
                    'maxBytes': 10485760,
                    'backupCount': 5,
                    'encoding': 'utf-8',
                    'formatter': 'file',
                },
            },
            'formatters': {
                'file': {
                    'format': self.log_format,
                    'datefmt': '%Y/%m/%d %H:%M:%S',
                },
                'zettarepl_file': {
                    'format': '[%(asctime)s] %(levelname)-8s [%(threadName)s] [%(name)s] %(message)s',
                    'datefmt': '%Y/%m/%d %H:%M:%S',
                },
            },
        }

    def getLogger(self):
        return logging.getLogger(self.application_name)

    def stream(self):
        for handler in logging.root.handlers:
            if isinstance(handler, ErrorProneRotatingFileHandler):
                return handler.stream

    def _set_output_file(self):
        """Set the output format for file log."""
        try:
            os.makedirs(os.path.dirname(FAILOVER_LOGFILE), mode=0o755, exist_ok=True)
            dictConfig(self.DEFAULT_LOGGING)
        except Exception:
            # If something happens during system dataset reconfiguration, we have the chance of not having
            # /var/log present leaving us with "ValueError: Unable to configure handler 'file':
            # [Errno 2] No such file or directory: '/var/log/middlewared.log'"
            # crashing the middleware during startup
            pass
        # Make sure log file is not readable by everybody.
        # umask could be another approach but chmod was chosen so
        # it affects existing installs.
        try:
            os.chmod(LOGFILE, 0o640)
        except OSError:
            pass
        try:
            os.chmod(ZETTAREPL_LOGFILE, 0o640)
        except OSError:
            pass

    def _set_output_console(self):
        """Set the output format for console."""

        console_handler = logging.StreamHandler()
        logging.root.setLevel(getattr(logging, self.debug_level))
        time_format = "%Y/%m/%d %H:%M:%S"
        console_handler.setFormatter(LoggerFormatter(self.log_format, datefmt=time_format))

        logging.root.addHandler(console_handler)

    def configure_logging(self, output_option='file'):
        """Configure the log output to file or console.

            Args:
                    output_option (str): Default is `file`, can be set to `console`.
        """

        if output_option.lower() == 'console':
            self._set_output_console()
        else:
            self._set_output_file()

        logging.root.setLevel(getattr(logging, self.debug_level))


def setup_logging(name, debug_level, log_handler):
    _logger = Logger(name, debug_level)
    _logger.getLogger()

    if 'file' in log_handler:
        _logger.configure_logging('file')
        stream = _logger.stream()
        if stream is not None:
            sys.stdout = sys.stderr = stream
    elif 'console' in log_handler:
        _logger.configure_logging('console')
    else:
        _logger.configure_logging('file')


def reconfigure_logging(handler_name='file'):
    handler = logging._handlers.get(handler_name)
    if handler:
        stream = handler.stream
        handler.stream = handler._open()
        if handler_name == 'file':
            # We want to reassign stdout/stderr if its not the default one or closed
            # which will happen on log file rotation.
            try:
                if sys.stdout.fileno() != 1 or sys.stderr.fileno() != 2:
                    raise ValueError()
            except ValueError:
                # ValueError can be raise if file handler is closed
                sys.stdout = handler.stream
                sys.stderr = handler.stream
        try:
            stream.close()
        except Exception:
            pass
