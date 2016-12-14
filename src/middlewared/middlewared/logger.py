import os
import logging
import rollbar
from .utils import sw_version_is_stable


class Rollbar(object):

    def __init__(self):
        self.logger = logging.getLogger('application')
        rollbar.init(
            'caf06383cba14d5893c4f4d0a40c33a9',
            'production' if 'DEVELOPER_MODE' not in os.environ else 'development'
            )

    def rollbar_report(self, exc_info, sw_version):

        log_path = (('/var/log/middlewared.log', 'middlewared_log'),)

        # Allow rollbar to be disabled via sentinel file or environment var,
        # if FreeNAS current train is STABLE, the sentinel file path will be /tmp/,
        # otherwise it's path will be /data/ and can be persistent.
        sentinel_file_path = '/data/.rollbar_disabled'
        if sw_version_is_stable():
            sentinel_file_path = '/tmp/.rollbar_disabled'

        if (os.path.exists(sentinel_file_path) or 'ROLLBAR_DISABLED' in os.environ):
            self.logger.debug('rollbar is disabled using sentinel file: {0}'.format(sentinel_file_path))
            return

        extra_data = {}
        try:
            extra_data['sw_version'] = sw_version
        except:
            self.logger.debug('Failed to get system version', exc_info=True)

        for path, name in log_path:
            if os.path.exists(path):
                with open(path, 'r') as absolute_file_path:
                    extra_data[name] = absolute_file_path.read()[-10240:]
        rollbar.report_exc_info(exc_info, extra_data=extra_data)
