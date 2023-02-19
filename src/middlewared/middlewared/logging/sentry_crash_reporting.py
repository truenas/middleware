import os
import logging

import sentry_sdk

from middlewared.utils import MIDDLEWARE_RUN_DIR, sw_info

DISABLED_SENTINEL = '.crashreporting_disabled'
DISABLED_KEY = 'CRASHREPORTING_DISABLED'
MAX_STRING_LEN = 10240


class SentryCrashReporting:
    """Sentry class for reporting crash info to a remote endpoint"""
    enabled_in_settings = False

    def __init__(self):
        self.logger = logging.getLogger('middlewared.logging.SentryCrashReporting')
        self.init_sentry_sdk()

    def init_sentry_sdk(self):
        dsn = 'https://11101daa5d5643fba21020af71900475:d60cd246ba684afbadd479653de2c216@sentry.ixsystems.com/2'
        query = '?timeout=3'
        dsn = f'{dsn}{query}'
        release = sw_info()['fullname']
        sentry_sdk.init(dsn=dsn, release=release, default_integrations=False)
        sentry_sdk.utils.MAX_STRING_LENGTH = MAX_STRING_LEN

    def is_disabled(self):
        """
        Sentry Crash reporting can be disabled via:
            1. system_settings table in the db or
            2. presence of sentifnel file (`DISABLED_SENTINEL`) or
            3. environment variable (`DISABLED_KEY`)
        """
        if not self.enabled_in_settings:
            # disabed in db
            return True
        elif os.path.exists(os.path.join(MIDDLEWARE_RUN_DIR if sw_info()['stable'] else '/data', DISABLED_SENTINEL)):
            # disabled because of presence of sentinel file
            return True
        elif os.environ.get(DISABLED_KEY, False):
            # disabled via environment variable
            return True
        elif os.stat(__file__).st_dev != os.stat('/').st_dev:
            # middlewared package directory is remotely mounted
            # (i.e. done by some developers)
            return True
        else:
            return False

    def get_log_file_content(self, log_files):
        data = dict()
        for path, name in log_files:
            try:
                with open(path, 'rb') as f:
                    # seek to offset relative to the end of file
                    # since we don't want to load the entire contents
                    # into memory as a single string just to read the
                    # last `MAX_STRING_LEN` chars...
                    f.seek(-MAX_STRING_LEN, os.SEEK_END)
                    data[name] = f.read().decode()
            except FileNotFoundError:
                continue

        return data

    def report(self, exc_info, log_files):
        """"
        Args:
            exc_info (tuple): Same as sys.exc_info().
            log_files (tuple): A tuple with log file absolute path and name.
        """
        if self.is_disabled():
            return

        self.logger.debug('Sending a crash report...')
        try:
            with sentry_sdk.configure_scope() as scope:
                payload_size = 0
                for k, v in self.get_log_file_content(log_files).items():
                    if payload_size + len(v) < 190000:
                        scope.set_extra(k, v)
                        payload_size += len(v)
                sentry_sdk.capture_exception(exc_info)
        except Exception:
            self.logger.debug('Failed to send crash report', exc_info=True)
