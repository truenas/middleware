import datetime

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

WEBUI_SUPPORT_FORM = 'Please contact iXsystems Support using the form in System -> Support'


class NVDIMMAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'There Is An Issue With NVDIMM'
    text = 'NVDIMM: "%(dev)s" is reporting "%(value)s" with status "%(status)s".'
    products = ('ENTERPRISE',)


class NVDIMMLifetimeWarningAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'NVDIMM Memory Module Lifetime Is Less Than 20%'
    text = 'NVDIMM: "%(dev)s" Memory Module Remaining Lifetime is %(value)d%%.'
    products = ('ENTERPRISE',)


class NVDIMMLifetimeCriticalAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = 'NVDIMM Memory Module Lifetime Is Less Than 10%'
    text = 'NVDIMM: "%(dev)s" Memory Module Remaining Lifetime is %(value)d%%.'
    products = ('ENTERPRISE',)


class NVDIMMInvalidFirmwareVersionAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = 'Invalid NVDIMM Firmware Version'
    text = f'NVDIMM: "%(dev)s" is running invalid firmware. {WEBUI_SUPPORT_FORM}'
    products = ('ENTERPRISE',)
    proactive_support = True


class NVDIMMRecommendedFirmwareVersionAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = 'NVDIMM Firmware Version Should Be Upgraded'
    text = (
        'NVDIMM: "%(dev)s" is running firmware version "%(rv)s" which can be upgraded to '
        f'"%(uv)s". {WEBUI_SUPPORT_FORM}'
    )
    products = ('ENTERPRISE',)
    proactive_support = True


class OldBiosVersionAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'Old BIOS Version'
    text = f'This system is running an old BIOS version. {WEBUI_SUPPORT_FORM}'
    products = ('ENTERPRISE',)
    proactive_support = True


class NVDIMMAndBIOSAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(datetime.timedelta(minutes=5))
    products = ('ENTERPRISE',)

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

        if (val := int(nvdimm['nvm_lifetime'].rstrip('%'))) < 20:
            alert = NVDIMMLifetimeWarningAlertClass if val > 10 else NVDIMMLifetimeCriticalAlertClass
            alerts.append(Alert(alert, {'dev': 'NVM Lifetime', 'value': val}))

        if nvdimm['index'] == 0 and (val := int(nvdimm['es_lifetime'].rstrip('%'))) < 20:
            # we only check this value for the 0th slot nvdimm since M60 has 2 and the way
            # they're physically cabled, prevents monitoring the 2nd nvdimm's energy source
            # (it always reports -1%)
            alert = NVDIMMLifetimeWarningAlertClass if val > 10 else NVDIMMLifetimeCriticalAlertClass
            alerts.append(Alert(alert, {'dev': 'NVM Energy Source', 'value': val}))

        if (run_fw := nvdimm['running_firmware']) is not None:
            if run_fw not in nvdimm['qualified_firmware']:
                alerts.append(Alert(NVDIMMInvalidFirmwareVersionAlertClass, {'dev': dev}))
            elif run_fw != nvdimm['recommended_firmware']:
                alerts.append(Alert(
                    NVDIMMRecommendedFirmwareVersionAlertClass,
                    {'dev': dev, 'rv': run_fw, 'uv': nvdimm['recommended_firmware']}
                ))

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
