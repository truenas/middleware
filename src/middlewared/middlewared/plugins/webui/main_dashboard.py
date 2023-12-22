from datetime import timedelta
from time import clock_gettime, CLOCK_MONOTONIC_RAW

from middlewared.schema import accepts
from middlewared.service import Service
from middlewared.utils import sw_info


class WebUIMainDashboardService(Service):
    class Config:
        namespace = 'webui.main.dashboard'
        cli_private = True
        private = True

    def sys_info_impl(self):
        dmi = self.middleware.call_sync('system.dmidecode_info')
        platform = 'Generic'
        if dmi['system-product-name'].startswith(('FREENAS-', 'TRUENAS-')):
            platform = dmi['system-product-name']

        # we query database table directly because using the standard
        # `network.configuration.config` is just too slow and too heavy
        # for simply determining the hostname.
        # NOTE: we show what is written to the database which doesn't
        # necessarily mean that's what the hostname is on OS side
        nc = self.middleware.call_sync('datastore.query', 'network.globalconfiguration')
        if self.middleware.call_sync('failover.node') in ('A', 'MANUAL'):
            hostname = nc[0]['gc_hostname']
        else:
            hostname = nc[0]['gc_hostname_b']

        return {
            'platform': platform,
            'version': sw_info()['fullname'],
            'license': self.middleware.call_sync('system.license'),
            'system_serial': dmi['system-serial-number'],
            'hostname': hostname,
            'uptime': str(timedelta(seconds=clock_gettime(CLOCK_MONOTONIC_RAW))),
        }

    @accepts()
    def sys_info(self):
        """This endpoint was designed to be exclusively
        consumed by the webUI team. This is what makes
        up the System Information card on the main
        dashboard after a user logs in.
        """
        info = self.sys_info_impl()
        try:
            info['remote_info'] = self.middleware.call_sync(
                'failover.call_remote', 'webui.main.dashboard.sys_info_impl'
            )
        except Exception:
            # could be ENOMETHOD (fresh upgrade) or we could
            # be on a non-HA system. Either way, doesn't matter
            # we just need to try and get the information and
            # set the key to None if we fail
            info['remote_info'] = None

        return info
