import os
import logging
import rollbar
from .utils import sw_version_is_stable


class Rollbar(object):
    """Pseudo-Class for Rollbar - Error Tracking Software."""

    def __init__(self):
        self.sentinel_file_path = '/data/.rollbar_disabled'
        self.logger = logging.getLogger('application')
        rollbar.init(
            'caf06383cba14d5893c4f4d0a40c33a9',
            'production' if 'DEVELOPER_MODE' not in os.environ else 'development'
            )

    def is_rollbar_disabled(self):
        """Check the existence of sentinel file and its absolute path
           against STABLE and DEVELOPMENT branches.

           Returns:
                       bool: True if rollbar is disabled, False otherwise.
        """
        # Allow rollbar to be disabled via sentinel file or environment var,
        # if FreeNAS current train is STABLE, the sentinel file path will be /tmp/,
        # otherwise it's path will be /data/ and can be persistent.
        if sw_version_is_stable():
            self.sentinel_file_path = '/tmp/.rollbar_disabled'

        if (os.path.exists(self.sentinel_file_path) or 'ROLLBAR_DISABLED' in os.environ):
            self.logger.debug('rollbar is disabled using sentinel file: {0}'.format(self.sentinel_file_path))
            return True
        else:
            return False

    def rollbar_report(self, exc_info, request, sw_version, t_log_files):
        """"Wrapper for rollbar.report_exc_info.

        Args:
                    exc_info (tuple): Same as sys.exc_info().
                    request (obj, optional): It is the HTTP Request.
                    sw_version (str): The current middlewared version.
                    t_log_files (tuple): A tuple with log file absolute path and name.
        """
        if self.is_rollbar_disabled():
            return

        extra_data = {}
        try:
            extra_data['sw_version'] = sw_version
        except:
            self.logger.debug('Failed to get system version', exc_info=True)

        if all(t_log_files):
            for path, name in t_log_files:
                if os.path.exists(path):
                    with open(path, 'r') as absolute_file_path:
                        extra_data[name] = absolute_file_path.read()[-10240:]

        try:
            rollbar.report_exc_info(exc_info, request if request is not None else "", extra_data=extra_data)
        except:
            self.logger.warn('[Rollbar] Failed to report error.', exc_info=True)
