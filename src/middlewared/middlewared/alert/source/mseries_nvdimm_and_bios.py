import subprocess
import json
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


class NVDIMMUnknownModelAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'Unknown NVDIMM Model'
    text = 'Unknown NVDIMM Model: dev: "%(dev)s" %(size)dGB %(clock_speed)dMHz'
    products = ('SCALE_ENTERPRISE',)


class NVDIMMUnknownFirmwareAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'Unknown NVDIMM Firmware Version'
    text = 'Unknown NVDIMM Firmware Version: dev: "%(dev)s" firmware version: "%(fwver)s"'
    products = ('SCALE_ENTERPRISE',)


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

    def get_ndctl_output(self):
        output = []
        try:
            rv = subprocess.run(['ndctl', 'list', '-D', '--health'], stdout=subprocess.PIPE)
            output = json.loads(rv.stdout.decode())
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            self.middleware.logger.warning('Failed to query health information for nvdimm(s).', exc_info=True)

        return output

    def generate_lifetime_alerts_and_get_health_states(self, alerts, health_states):
        for nvdimm in self.get_ndctl_output():
            lifetime = 100 - nvdimm['health']['life_used_percentage']
            alert = None
            if lifetime < 10:
                alert = NVDIMMLifetimeCriticalAlertClass
            elif lifetime < 20:
                alert = NVDIMMLifetimeWarningAlertClass

            if alert is not None:
                alerts.append(Alert(alert, {'dev': nvdimm['dev'], 'value': lifetime}))

            health_states[nvdimm['dev']] = nvdimm['health']['health_state']

    def generate_firmware_and_health_state_and_bios_alerts(self, alerts, health_states, old_bios):
        model_to_fw = {
            (16, 2666): ['2.1', '2.2', '2.4'],
            (16, 2933): ['2.2'],
            (32, 2933): ['2.4'],
        }
        old_bios_alert_already_generated = old_bios
        for i in self.middleware.call_sync('mseries.nvdimm.info'):
            model = (i['size'], i['clock_speed'])
            if model not in model_to_fw:
                alerts.append(Alert(
                    NVDIMMUnknownModelAlertClass,
                    {'dev': i['dev'], 'size': i['size'], 'clock_speed': i['clock_speed']}
                ))
            elif i['firmware_version'] is None:
                alerts.append(Alert(
                    NVDIMMUnknownFirmwareAlertClass,
                    {'dev': i['dev'], 'fwver': 'UNKNOWN'}
                ))
            else:
                if i['firmware_version'] not in model_to_fw[model]:
                    alerts.append(Alert(NVDIMMFirmwareVersionAlertClass, {'dev': i['dev']}))

                if (value := health_states.get(i['dev'])) is not None and value != 'ok':
                    alerts.append(Alert(
                        NVDIMMAlertClass,
                        {'dev': i['dev'], 'value': value, 'status': i['module_health']}
                    ))

                if not old_bios_alert_already_generated and i['old_bios']:
                    alerts.append(Alert(OldBiosVersionAlertClass))
                    old_bios_alert_already_generated = True

    def check_sync(self):
        alerts = []
        health_states = {}
        sys = ('TRUENAS-M40', 'TRUENAS-M50', 'TRUENAS-M60')
        if self.middleware.call_sync('truenas.get_chassis_hardware').startswith(sys):
            old_bios = self.middleware.call_sync('mseries.bios.is_old_version')
            if old_bios:
                alerts.append(Alert(OldBiosVersionAlertClass))

            self.generate_lifetime_alerts_and_get_health_states(alerts, health_states)
            self.generate_firmware_and_health_state_and_bios_alerts(alerts, health_states, old_bios)

        return alerts
