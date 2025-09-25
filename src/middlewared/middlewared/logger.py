import logging
import logging.handlers
import queue
import socket
import typing
import warnings
from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from json import dumps

from cryptography.utils import CryptographyDeprecationWarning

from .utils.time_utils import utc_now


# Set logging levels
for level, names in {
    logging.INFO: (
        'charset_normalizer',  # "Encoding detection: ascii is most likely the one."
        'MARKDOWN',  # markdown debug is also considered useless
        'paramiko',  # It's too verbose (when used to list remote datasets/snapshots)
    ),
    logging.WARNING: (
        'acme.client',  # ACME is very verbose in logging the request it sends with headers etc, let's not pollute the
                        # logs with that much information and raise the log level in this case
        'aiohttp.internal',  # We dont need internal aiohttp debug logging
        'asyncio',  # asyncio runs in debug mode but we do not need INFO/DEBUG
        'botocore',  # We dont need internal botocore debug logging
        'certbot_dns_cloudflare._internal.dns_cloudflare',
        'urllib3',
        'websocket',  # we dont need websocket debug messages
    ),
    logging.ERROR: (
        'docker.auth',
        'docker.utils.config',  # Prevent debug docker logs
        'googleapiclient',  # issues garbage warnings
        'httpx._client',  # Prevent httpx debug spam
        'kmip.services.kmip_client',  # Prevent kmip client spam
    ),
    logging.CRITICAL: (
        'pyroute2.ndb',  # pyroute2.ndb is chatty....only log errors
        'pyroute2.netlink',
        'pyroute2.netlink.nlsocket',
    ),
}.items():
    for name in names:
        logging.getLogger(name).setLevel(level)


# /usr/lib/python3/dist-packages/pydantic/json_schema.py:2158: PydanticJsonSchemaWarning:
# Default value <object object at 0x7fa8ac040d30> is not JSON serializable; excluding default from JSON schema
# [non-serializable-default]
# This default value is `middlewared.utils.lang.undefined`. It must be there for our
# `middlewared.api.base.ForUpdateMetaclass` to work so this warning is false positive.
# Excluding this default from the generated JSON schema is the correct behavior, so there is no real issue here.
warnings.filterwarnings("ignore", module="pydantic.json_schema")

# asyncssh imports various weak crypto algorithms generating log spam on every middleware start
warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

logging.TRACE = 6

APP_LIFECYCLE_LOGFILE = '/var/log/app_lifecycle.log'
APP_MIGRATION_LOGFILE = '/var/log/app_migrations.log'
DOCKER_IMAGE_LOGFILE = '/var/log/docker_image.log'
FAILOVER_LOGFILE = '/var/log/failover.log'
LOGFILE = '/var/log/middlewared.log'
DEFAULT_LOGFORMAT = '[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s():%(lineno)d - %(message)s'
FALLBACK_LOGFILE = '/var/log/fallback-middlewared.log'
NETDATA_API_LOGFILE = '/var/log/netdata_api.log'
NGINX_LOG_PATH = '/var/log/nginx'
TRUENAS_CONNECT_LOGFILE = '/var/log/truenas_connect.log'
ZETTAREPL_LOGFILE = '/var/log/zettarepl.log'
ZETTAREPL_LOGFORMAT = '[%(asctime)s] %(levelname)-8s [%(threadName)s] [%(name)s] %(message)s'

DEFAULT_IDENT = 'MIDDLEWARE: '
MIDDLEWARE_AUDIT_IDENT = 'TNAUDIT_MIDDLEWARE: '
DEFAULT_SYSLOG_PATH = '/var/run/syslog-ng/middleware.sock'
DEFAULT_PENDING_QUEUE_LEN = 4096


def trace(self, message, *args, **kws):
    if self.isEnabledFor(logging.TRACE):
        self._log(logging.TRACE, message, args, **kws)


logging.addLevelName(logging.TRACE, "TRACE")
logging.Logger.trace = trace


@dataclass(slots=True, frozen=True)
class TNLog:
    name: str | None
    logfile: str
    logformat: str = DEFAULT_LOGFORMAT
    pending_maxlen: int | None = DEFAULT_PENDING_QUEUE_LEN

    def get_ident(self):
        if self.name is None:
            return DEFAULT_IDENT

        return f'{self.name.upper()}: '


# NOTE if new separate log file needs to be added, create a new TNLog
# object and append to ALL_LOG_FILES tuple. These files are read by the
# syslog-ng config generation scripts and automatically handled.
TNLOG_MIDDLEWARE = TNLog(None, LOGFILE)
TNLOG_APP_LIFECYCLE = TNLog('app_lifecycle', APP_LIFECYCLE_LOGFILE)
TNLOG_APP_MIGRATION = TNLog('app_migration', APP_MIGRATION_LOGFILE)
TNLOG_DOCKER_IMAGE = TNLog('docker_image', DOCKER_IMAGE_LOGFILE)
TNLOG_FAILOVER = TNLog('failover', FAILOVER_LOGFILE)
TNLOG_NETDATA_API = TNLog('netdata_api', NETDATA_API_LOGFILE)
TNLOG_TNC = TNLog('truenas_connect', TRUENAS_CONNECT_LOGFILE)
TNLOG_ZETTAREPL = TNLog('zettarepl', ZETTAREPL_LOGFILE, ZETTAREPL_LOGFORMAT)

# NOTE: this is also consumed by tests/unit/test_logger.py, which validates
# the auto-generated syslog-ng rules place messages in the correct log files.
ALL_LOG_FILES = (
    TNLOG_MIDDLEWARE,
    TNLOG_APP_LIFECYCLE,
    TNLOG_APP_MIGRATION,
    TNLOG_DOCKER_IMAGE,
    TNLOG_FAILOVER,
    TNLOG_NETDATA_API,
    TNLOG_TNC,
    TNLOG_ZETTAREPL,
)

# Audit entries are inserted into audit databases in /audit rather than
# written to files in /var/log and so they are not members of ALL_LOG_FILES
MIDDLEWARE_TNAUDIT = TNLog('TNAUDIT_MIDDLEWARE', '', '', None)

BASIC_SYSLOG_TRANSLATION = str.maketrans({'\n': '\\n'})


class TNLogFormatter(logging.Formatter):
    """ logging formatter to convert python exception into structured data """

    def _escape_rfc_generic(self, msg: str) -> str:
        return msg.translate(BASIC_SYSLOG_TRANSLATION)

    def format(self, record: logging.LogRecord) -> str:
        exc_info = record.exc_info
        exc_text = record.exc_text
        stack_info = record.stack_info
        structured_data = {}

        record.exc_info = None
        record.exc_text = None
        record.stack_info = None

        # Generate message following formatter rules
        # Then collapse to single line for sending to syslog.
        msg = self._escape_rfc_generic(super().format(record))
        if exc_info:
            structured_data['exception'] = self.formatException(exc_info)

        if stack_info:
            structured_data['stack'] = self.formatStack(stack_info)

        if structured_data:
            structured_data['type'] = 'PYTHON_EXCEPTION'
            structured_data['time'] = utc_now().strftime('%Y-%m-%d %H:%M:%S.%f')
            json_data = dumps({'TNLOG': structured_data})
            msg += f' @cee:{json_data}'

        record.exc_info = exc_info
        record.exc_text = exc_text
        record.stack_info = stack_info
        return msg


class ConsoleLogFormatter(logging.Formatter):
    """Format the console log messages"""

    class ConsoleColor(StrEnum):
        YELLOW  = '\033[1;33m'  # (warning)
        GREEN   = '\033[1;32m'  # (info)
        RED     = '\033[1;31m'  # (error)
        HIGHRED = '\033[1;41m'  # (critical)
        RESET   = '\033[1;m'    # Reset

    def format(self, record):
        """Set the color based on the log level.

            Returns:
                logging.Formatter class.
        """
        ConsoleColor = self.ConsoleColor
        color_mapping = {
            logging.CRITICAL: ConsoleColor.HIGHRED,
            logging.ERROR   : ConsoleColor.HIGHRED,
            logging.WARNING : ConsoleColor.RED,
            logging.INFO    : ConsoleColor.GREEN,
            logging.DEBUG   : ConsoleColor.YELLOW,
        }

        color_start = color_mapping.get(record.levelno, ConsoleColor.RESET)
        record.levelname = color_start + record.levelname + ConsoleColor.RESET

        return logging.Formatter.format(self, record)


QFORMATTER = TNLogFormatter()


class TNSyslogHandler(logging.handlers.SysLogHandler):
    def __init__(
        self,
        address: str = DEFAULT_SYSLOG_PATH,
        pending_queue: deque | None = None
    ):
        """
        address - path to Unix socket (should be defined in syslog-ng config)

        pending_queue - deque object that will be used for storing failed
        LogRecords if syslog is currently down.

        Note: maxlen should be set unless one wants to queue the log messages
        without loss until syslog connection restored. This is probably
        desireable for auditing, but not for general purposes (where it's
        better to just specify a fallback handler).
        """
        self.pending_queue = pending_queue
        self.fallback_handler = None
        super().__init__(address, socktype=socket.SOCK_STREAM)

    def drain_pending_queue(self) -> bool:
        """
        Attempt to emit any log records that have been queued up due to logging
        failures to the syslog socket.

        Returns:
            True if successfully drained entire queue else False

        Raises:
            Should not raise exceptions
        """
        while self.pending_queue:
            record = self.pending_queue.popleft()
            try:
                super().emit(record)
            except Exception:
                # Nope. Still dead. Put it back where we found it
                self.pending_queue.appendleft(record)
                return False

        return True

    def fallback(self, record: logging.LogRecord) -> None:
        """
        Fallback logging mechanism in case the syslog target is down.

        In this case we emit the log record to the fallback handler and ignore
        any errors.

        Returns:
            None

        Raises:
            Should not raise exceptions
        """
        if not self.fallback_handler:
            return

        try:
            self.fallback_handler.emit(record)
        except Exception:
            pass

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a LogRecord to syslog. If this fails then add to pending queue and
        emit via our fallback handler.
        """

        # First attempt to drain the pending queue
        if not self.drain_pending_queue():
            # Failed to drain our pending queue so add this record to the
            # ever-growing deque
            self.pending_queue.append(record)
            self.fallback(record)
            return

        try:
            super().emit(record)
        except Exception:
            # logging framework done broke. Queue up
            # for drain on next auditd message handled
            self.pending_queue.append(record)
            self.fallback(record)

    def handleError(self, record: logging.LogRecord) -> None:
        """
        Override the default syslog error handler if we have a pending_queue to
        defined. Exception raised here passes back up to the the emit() call.
        """
        # re-raise it back up to the emit call
        if self.pending_queue is None:
            return super().handleError(record)

        raise

    def set_fallback_handler(self, fallback: logging.Handler) -> None:
        """ Set a fallback handler (for example to file) that will be used if syslog socket logging fails """
        if not isinstance(fallback, logging.Handler):
            raise TypeError(f'{fallback}: not a logging.Handler')

        self.fallback_handler = fallback

    def close(self) -> None:
        # Close our socket
        super().close()

        if self.fallback_handler:
            # close any open file handler
            self.fallback_handler.close()
            self.fallback_handler = None


def setup_syslog_handler(tnlog: TNLog, fallback: logging.Handler | None) -> logging.Logger:
    # Use `QueueHandler` to avoid blocking IO in asyncio main loop
    log_queue = queue.Queue()
    queue_handler = logging.handlers.QueueHandler(log_queue)

    # We need to handle python exceptions (format into structured data)
    # rather than allowing the QueueHandler to perform exception formatting,
    queue_handler.setFormatter(QFORMATTER)

    # Set up syslog handler with deque to store failed messages until
    # they can be flushed. This can happen if syslog-ng isn't ready yet.
    syslog_handler = TNSyslogHandler(pending_queue=deque(maxlen=tnlog.pending_maxlen))
    syslog_handler.setLevel(logging.DEBUG)

    if tnlog.logformat:
        syslog_handler.setFormatter(logging.Formatter(tnlog.logformat, '%Y/%m/%d %H:%M:%S'))

    # Set ident for the logger. This becomes program name in syslog-ng and allows
    # more precise filtering rules
    syslog_handler.ident = tnlog.get_ident()

    # Set fallback for case where syslog is broken. This does not need separate queue
    # since emit will happen in separate thread from main loop.
    if fallback:
        syslog_handler.set_fallback_handler(fallback)

    queue_listener = logging.handlers.QueueListener(log_queue, syslog_handler)
    queue_listener.start()
    logger = logging.getLogger(tnlog.name)
    logger.addHandler(queue_handler)
    if tnlog.name is not None:
        logging.getLogger(tnlog.name).propagate = False

    return logger


class Logger:
    """Pseudo-Class for Logger - Wrapper for logging module"""
    def __init__(self, application_name: str, debug_level: str = 'DEBUG', log_format: str = DEFAULT_LOGFORMAT):
        self.application_name = application_name
        self.debug_level = debug_level
        self.log_format = log_format

    def getLogger(self):
        return logging.getLogger(self.application_name)

    def configure_logging(self, output_option: str):
        """
        Configure the log output to file or console.
            `output_option` str: Default is `file`, can be set to `console`.
        """
        if output_option.lower() == 'console':
            console_handler = logging.StreamHandler()
            logging.root.setLevel(getattr(logging, self.debug_level))
            time_format = "%Y/%m/%d %H:%M:%S"
            console_handler.setFormatter(ConsoleLogFormatter(self.log_format, datefmt=time_format))
            logging.root.addHandler(console_handler)
        else:
            # Set up our fallback logging mechanism (to file) in case syslog is broken
            # We internally queue writes to regular log files while waiting for syslog to recover
            # while simultaneously writing to the fallback file so that there is less potential to
            # lose relevant logs.
            fallback_handler = logging.handlers.RotatingFileHandler(FALLBACK_LOGFILE, 'a', 10485760, 5, 'utf-8')
            fallback_handler.setLevel(logging.DEBUG)
            fallback_handler.setFormatter(logging.Formatter(DEFAULT_LOGFORMAT, '%Y/%m/%d %H:%M:%S'))

            for tnlog in ALL_LOG_FILES:
                setup_syslog_handler(tnlog, fallback_handler)

        logging.root.setLevel(getattr(logging, self.debug_level))


def setup_audit_logging() -> logging.Logger:
    return setup_syslog_handler(MIDDLEWARE_TNAUDIT, None)


def setup_logging(name: str, debug_level: typing.Optional[str], log_handler: typing.Optional[str]):
    _logger = Logger(name, debug_level)
    _logger.getLogger()

    if log_handler == 'console':
        _logger.configure_logging('console')
    else:
        _logger.configure_logging('file')
