import datetime

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule


class NVDIMMAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'There Is An Issue With NVDIMM'
    text = 'NVDIMM: "%(dev)s" is reporting "%(value)s" with status "%(status)s".'
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


class NVDIMMFirmwareVersionAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = 'Invalid NVDIMM Firmware Version'
    text = (
        'NVDIMM: "%(dev)s" is using a firmware version which can cause data loss if a power outage '
        'event occurs. Please contact iXsystems Support using the form in System -> Support.'
    )
    products = ('SCALE_ENTERPRISE',)
    proactive_support = True


class OldBiosVersionAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'Old BIOS Version'
    text = (
        'This system is running an old BIOS version. Please contact iXsystems Support '
        'using the form in System > Support'
    )
    products = ('SCALE_ENTERPRISE',)
    proactive_support = True


class NVDIMMAndBIOSAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(datetime.timedelta(minutes=5))
    products = ('SCALE_ENTERPRISE',)

    def produce_alerts(self, nvdimm, alerts, old_bios):
        persistency_restored = 0x4
        arm_info = 0x40
        dev = nvdimm['dev']
        old_bios_alert_already_generated = old_bios
        for _hex, vals in nvdimm['critical_health_info'].items():
            hex_int = int(_hex, 16)
            if hex_int & ~(persistency_restored | arm_info):
                alerts.append(Alert(
                    NVDIMMAlertClass,
                    {'dev': dev, 'value': _hex, 'status': ','.join(vals)}
                ))

            if nvdimm['specrev'] >= 22 and not (hex_int & arm_info):
                alerts.append(Alert(
                    NVDIMMAlertClass,
                    {'dev': dev, 'value': 'ARM_INFO', 'status': 'not set'}
                ))

        for i in ('nvm_health_info', 'nvm_error_threshold_status', 'nvm_warning_threshold_status'):
            for _hex, vals in nvdimm[i].items():
                if int(_hex, 16) != 0:
                    alerts.append(Alert(
                        NVDIMMAlertClass,
                        {'dev': dev, 'value': _hex, 'status': ','.join(vals)}
                    ))

        for i in ('nvm_lifetime', 'es_lifetime'):
            val = int(nvdimm[i].rstrip('%'))
            if val < 20:
                alert = NVDIMMLifetimeWarningAlertClass if val > 10 else NVDIMMLifetimeCriticalAlertClass
                name = dev if i == 'nvm_lifetime' else 'nvm energy source'
                alerts.append(Alert(alert, {'dev': name, 'value': val}))

        if nvdimm['running_firmware'] not in nvdimm['qualified_firmware']:
            alerts.append(Alert(NVDIMMFirmwareVersionAlertClass, {'dev': dev}))

        if not old_bios_alert_already_generated and nvdimm['old_bios']:
            alerts.append(Alert(OldBiosVersionAlertClass))
            old_bios_alert_already_generated = True

    def check_sync(self):
        alerts = []
        sys = ('TRUENAS-M40', 'TRUENAS-M50', 'TRUENAS-M60')
        if self.middleware.call_sync('truenas.get_chassis_hardware').startswith(sys):
            old_bios = self.middleware.call_sync('mseries.bios.is_old_version')
            if old_bios:
                alerts.append(Alert(OldBiosVersionAlertClass))

            for nvdimm in self.middleware.call_sync('mseries.nvdimm.info'):
                self.produce_alerts(nvdimm, alerts, old_bios)

        return alerts
