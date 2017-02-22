import os
import logging
import logging.handlers
from logging.config import dictConfig


class LoggerFormatter(object):
    """Subclass for Logger()."""

    def __init__(self):
        self.get_level = None

    def __console_color(self):
        """Set the color based on the log level.

            Returns:
                color_start (str): Returns the color code.
        """
        if self.get_level == self.LOGGING_LEVEL['CRITICAL']:
            color_start = self.CONSOLE_COLOR_FORMATTER['HIGHRED']
        elif self.get_level == self.LOGGING_LEVEL['ERROR']:
            color_start = self.CONSOLE_COLOR_FORMATTER['RED']
        elif self.get_level == self.LOGGING_LEVEL['WARNING']:
            color_start = self.CONSOLE_COLOR_FORMATTER['YELLOW']
        elif self.get_level == self.LOGGING_LEVEL['INFO']:
            color_start = self.CONSOLE_COLOR_FORMATTER['GREEN']
        elif self.get_level == self.LOGGING_LEVEL['DEBUG']:
            color_start = self.CONSOLE_COLOR_FORMATTER['YELLOW']
        else:
            color_start = self.CONSOLE_COLOR_FORMATTER['RESET']

        return color_start

    def set_console_formatter(self):
        """Set the format of console output.

            Returns:
                console_formatter (class): Returns a class of logging.Formatter()
        """
        color_start = self.__console_color()
        color_reset = self.CONSOLE_COLOR_FORMATTER['RESET']

        console_formatter = logging.Formatter(
            "[%(asctime)s] " + color_start + "(%(levelname)s)" + color_reset + " [Module: %(module)s, Call: %(name)s -> %(funcName)s(): %(lineno)s] - %(message)s", "%Y/%m/%d %H:%M:%S")

        return console_formatter


class LoggerStream(object):

    def __init__(self, logger):
        self.logger = logger
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.debug(line.rstrip())


class Logger(LoggerFormatter):
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
                'format': '[%(asctime)s] (%(levelname)s) [Module: %(module)s, Call: %(name)s -> %(funcName)s(): %(lineno)s] - %(message)s',
                'datefmt': '%Y/%m/%d %H:%M:%S',
            },
        },
    }

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

    def __init__(self, application_name):
        self.get_level = None
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
        console_handler.setFormatter(self.set_console_formatter())

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
