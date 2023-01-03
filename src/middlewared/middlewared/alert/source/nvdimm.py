import subprocess
import json
import datetime

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule


class NVDIMMAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'There Is An Issue With NVDIMM'
    text = 'NVDIMM: "%(dev)s" is reporting "%(value)s".'
    products = ('SCALE_ENTERPRISE',)


class NVDIMMLifetimeWarningAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'NVDIMM Memory Module Lifetime Is Less Than 20%'
    text = 'NVDIMM: "%(dev)s" Memory Module Remaining Lifetime is %(value)d%%.'
    products = ('SCALE_ENTERPRISE',)


class NVDIMMLifetimeCriticalAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = 'NVDIMM Memory Module Lifetime Is Less Than 10%'
    text = 'NVDIMM: "%(dev)s" Memory Module Remaining Lifetime is %(value)d%%.'
    products = ('SCALE_ENTERPRISE',)


class NVDIMMAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(datetime.timedelta(minutes=5))
    products = ('SCALE_ENTERPRISE',)

    def get_ndctl_output(self):
        output = []
        try:
            rv = subprocess.run(['ndctl', 'list', '-D', '--health'], stdout=subprocess.PIPE)
            output = json.loads(rv.stdout.decode())
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            self.middleware.logger.warning('Failed to query health information for nvdimm(s).', exc_info=True)

        return output

    def check_sync(self):
        alerts = []
        if self.middleware.call_sync('failover.hardware') != 'BHYVE':
            for nvdimm in self.get_ndctl_output():
                lifetime = 100 - nvdimm['health']['life_used_percentage']
                alert = None
                if lifetime < 10:
                    alert = NVDIMMLifetimeCriticalAlertClass
                elif lifetime < 20:
                    alert = NVDIMMLifetimeWarningAlertClass

                if alert is not None:
                    alerts.append(Alert(alert, {'dev': nvdimm['dev'], 'value': lifetime}))

                overall = nvdimm['health']['health_state']
                if overall != 'ok':
                    alerts.append(Alert(NVDIMMAlertClass, {'dev': nvdimm['dev'], 'value': overall}))

        return alerts
