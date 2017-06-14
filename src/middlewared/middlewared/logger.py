import os
import logging
import logging.handlers

from logging.config import dictConfig
from .utils import sw_version, sw_version_is_stable

from raven import Client
from raven.transport.threaded import ThreadedHTTPTransport

# markdown debug is also considered useless
logging.getLogger('MARKDOWN').setLevel(logging.INFO)
# asyncio runs in debug mode but we do not need INFO/DEBUG
logging.getLogger('asyncio').setLevel(logging.WARN)


class CrashReporting(object):
    """
    Pseudo-Class for remote crash reporting
    """

    def __init__(self, transport='threaded'):
        if transport == 'threaded':
            transport = ThreadedHTTPTransport
        else:
            raise ValueError(f'Unknown transport: {transport}')

        if sw_version_is_stable():
            self.sentinel_file_path = '/tmp/.crashreporting_disabled'
        else:
            self.sentinel_file_path = '/data/.crashreporting_disabled'
        self.logger = logging.getLogger('middlewared.logger.CrashReporting')
        self.client = Client(
            dsn='https://11101daa5d5643fba21020af71900475:d60cd246ba684afbadd479653de2c216@sentry.ixsystems.com/2?timeout=3',
            install_sys_hook=False,
            install_logging_hook=False,
            string_max_length=10240,
            release=sw_version(),
        )

    def is_disabled(self):
        """
        Check the existence of sentinel file and its absolute path
        against STABLE and DEVELOPMENT branches.

        Returns:
            bool: True if crash reporting is disabled, False otherwise.
        """
        # Allow report to be disabled via sentinel file or environment var,
        # if FreeNAS current train is STABLE, the sentinel file path will be /tmp/,
        # otherwise it's path will be /data/ and can be persistent.

        if os.path.exists(self.sentinel_file_path) or 'CRASHREPORTING_DISABLED' in os.environ:
            return True
        else:
            return False

    def report(self, exc_info, data, t_log_files):
        """"
        Args:
            exc_info (tuple): Same as sys.exc_info().
            request (obj, optional): It is the HTTP Request.
            sw_version (str): The current middlewared version.
            t_log_files (tuple): A tuple with log file absolute path and name.
        """
        if self.is_disabled():
            return

        extra_data = {}
        if all(t_log_files):
            payload_size = 0
            for path, name in t_log_files:
                if os.path.exists(path):
                    with open(path, 'r') as absolute_file_path:
                        contents = absolute_file_path.read()[-10240:]
                        # There is a limit for the whole report payload.
                        # Lets skip the file if its hits areasonable limit.
                        if len(contents) + payload_size > 61440:
                            continue
                        extra_data[name] = contents
                        payload_size += len(contents)

        self.logger.debug('Sending a crash report...')
        try:
            self.client.captureException(exc_info=exc_info, data=data, extra=extra_data)
        except Exception:
            pass  # We don't care about the exception


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


class Logger(object):
    """Pseudo-Class for Logger - Wrapper for logging module"""
    DEFAULT_LOGGING = {
        'version': 1,
        'disable_existing_loggers': True,
        'root': {
            'level': 'NOTSET',
            'handlers': ['file'],
        },
        'handlers': {
            'file': {
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': '/var/log/middlewared.log',
                'mode': 'a',
                'maxBytes': 10485760,
                'backupCount': 5,
                'encoding': 'utf-8',
                'formatter': 'file',
            },
        },
        'formatters': {
            'file': {
                'format': '[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s():%(lineno)d - %(message)s',
                'datefmt': '%Y/%m/%d %H:%M:%S',
            },
        },
    }

    def __init__(self, application_name):
        self.application_name = application_name

    def getLogger(self):
        return logging.getLogger(self.application_name)

    def _set_output_file(self):
        """Set the output format for file log."""
        dictConfig(self.DEFAULT_LOGGING)

    def _set_output_console(self):
        """Set the output format for console."""

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        log_format = "[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s():%(lineno)d - %(message)s"
        time_format = "%Y/%m/%d %H:%M:%S"
        console_handler.setFormatter(LoggerFormatter(log_format, datefmt=time_format))

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

        logging.root.setLevel(logging.DEBUG)
