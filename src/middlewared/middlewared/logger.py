import logging
import logging.handlers
import os
import queue

from .logging.console_formatter import ConsoleLogFormatter

# markdown debug is also considered useless
logging.getLogger('MARKDOWN').setLevel(logging.INFO)
# asyncio runs in debug mode but we do not need INFO/DEBUG
logging.getLogger('asyncio').setLevel(logging.WARNING)
# We dont need internal aiohttp debug logging
logging.getLogger('aiohttp.internal').setLevel(logging.WARNING)
# We dont need internal botocore debug logging
logging.getLogger('botocore').setLevel(logging.WARNING)
# we dont need websocket debug messages
logging.getLogger('websocket').setLevel(logging.WARNING)
# issues garbage warnings
logging.getLogger('googleapiclient').setLevel(logging.ERROR)
# registered 'pbkdf2_sha256' handler: <class 'passlib.handlers.pbkdf2.pbkdf2_sha256'>
logging.getLogger('passlib.registry').setLevel(logging.INFO)
logging.getLogger('passlib.handlers').setLevel(logging.INFO)
logging.getLogger('passlib.utils.compat').setLevel(logging.INFO)
# pyroute2.ndb is chatty....only log errors
logging.getLogger('pyroute2.ndb').setLevel(logging.CRITICAL)
logging.getLogger('pyroute2.netlink').setLevel(logging.CRITICAL)
logging.getLogger('pyroute2.netlink.nlsocket').setLevel(logging.CRITICAL)
# It logs each call made to the k8s api server when in debug mode, so we set the level to warn
logging.getLogger('kubernetes_asyncio.client.rest').setLevel(logging.WARNING)
logging.getLogger('kubernetes_asyncio.config.kube_config').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
# ACME is very verbose in logging the request it sends with headers etc, let's not pollute the logs
# with that much information and raise the log level in this case
logging.getLogger('acme.client').setLevel(logging.WARNING)
logging.getLogger('certbot_dns_cloudflare._internal.dns_cloudflare').setLevel(logging.WARNING)
# "Encoding detection: ascii is most likely the one."
logging.getLogger('charset_normalizer').setLevel(logging.INFO)
logging.TRACE = 6

CONTAINER_IMAGES_LOGFILE = '/var/log/container_images.log'
FAILOVER_LOGFILE = '/var/log/failover.log'
K8S_API_LOGFILE = '/var/log/k8s_api.log'
LOGFILE = '/var/log/middlewared.log'
NETDATA_API_LOGFILE = '/var/log/netdata_api.log'
ZETTAREPL_LOGFILE = '/var/log/zettarepl.log'


def trace(self, message, *args, **kws):
    if self.isEnabledFor(logging.TRACE):
        self._log(logging.TRACE, message, args, **kws)


logging.addLevelName(logging.TRACE, "TRACE")
logging.Logger.trace = trace


class Logger:
    """Pseudo-Class for Logger - Wrapper for logging module"""
    def __init__(
        self, application_name, debug_level=None,
        log_format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s():%(lineno)d - %(message)s'
    ):
        self.application_name = application_name
        self.debug_level = debug_level or 'DEBUG'
        self.log_format = log_format

    def getLogger(self):
        return logging.getLogger(self.application_name)

    def configure_logging(self, output_option):
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
            for name, filename, log_format in [
                (None, LOGFILE, self.log_format),
                ('container_images', CONTAINER_IMAGES_LOGFILE, self.log_format),
                ('failover', FAILOVER_LOGFILE, self.log_format),
                ('k8s_api', K8S_API_LOGFILE, self.log_format),
                ('netdata_api', NETDATA_API_LOGFILE, self.log_format),
                ('zettarepl', ZETTAREPL_LOGFILE,
                 '[%(asctime)s] %(levelname)-8s [%(threadName)s] [%(name)s] %(message)s'),
            ]:
                self.setup_file_logger(name, filename, log_format)

        logging.root.setLevel(getattr(logging, self.debug_level))

    def setup_file_logger(self, name, filename, log_format):
        # Use `QueueHandler` to avoid blocking IO in asyncio main loop
        log_queue = queue.Queue()
        queue_handler = logging.handlers.QueueHandler(log_queue)
        file_handler = logging.handlers.RotatingFileHandler(filename, 'a', 10485760, 5, 'utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format, '%Y/%m/%d %H:%M:%S'))
        queue_listener = logging.handlers.QueueListener(log_queue, file_handler)
        queue_listener.start()
        logging.getLogger(name).addHandler(queue_handler)
        if name is not None:
            logging.getLogger(name).propagate = False

        # Make sure various log files are not readable by everybody.
        # umask could be another approach but chmod was chosen so
        # it affects existing installs.
        try:
            os.chmod(filename, 0o640)
        except OSError:
            pass


def setup_logging(name, debug_level, log_handler):
    _logger = Logger(name, debug_level)
    _logger.getLogger()

    if log_handler == 'console':
        _logger.configure_logging('console')
    else:
        _logger.configure_logging('file')
