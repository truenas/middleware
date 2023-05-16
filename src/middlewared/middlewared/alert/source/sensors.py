from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, AlertSource, Alert


class SensorAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Sensor Value Is Outside of Working Range"
    text = "Sensor %(name)s is %(relative)s %(level)s value: %(value)s %(event)s"
    products = ("SCALE_ENTERPRISE",)


class PowerSupplyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Power Supply Error"
    text = "%(psu)s is %(state)s showing: %(errors)s"
    products = ("SCALE_ENTERPRISE",)


class SensorsAlertSource(AlertSource):

    def should_alert(self):
        if self.middleware.call_sync('dmidecode_info')['system-product-name'].startswith('TRUENAS-R'):
            # r-series
            return True
        elif self.middleware.call_sync('failover.hardware') == 'ECHOWARP':
            # m-series
            return True

        return False

    async def check(self):
        alerts = []
        if not self.should_alert():
            return alerts

        for i in await self.middleware.call('ipmi.sensor.query'):
            if i['state'] != 'Nominal' and i['reading'] != 'N/A':
                if i['type'] == 'Power Supply' and i['event']:
                    alerts.append(Alert(
                        PowerSupplyAlertClass,
                        {'psu': i['name'], 'state': i['state'], 'errors': ', '.join(i['event'])}
                    ))
                elif (alert := await self.produce_sensor_alert(i)) is not None:
                    alerts.append(alert)

        return alerts

    async def produce_sensor_alert(self, sensor):
        reading = sensor['reading']
        for key in ('lower-non-recoverable', 'lower-critical', 'lower-non-critical'):
            if sensor[key] != 'N/A' and reading < sensor[key]:
                relative = 'below'
                level = 'recommended' if key == 'lower-non-critical' else 'critical'
                return Alert(SensorAlertClass, {
                    'name': sensor['name'],
                    'relative': relative,
                    'level': level,
                    'value': reading,
                    'event': ', '.join(sensor['event'])
                })

        for key in ('upper-non-recoverable', 'upper-critical', 'upper-non-critical'):
            if sensor[key] != 'N/A' and reading > sensor[key]:
                relative = 'above'
                level = 'recommended' if key == 'upper-non-critical' else 'critical'
                return Alert(SensorAlertClass, {
                    'name': sensor['name'],
                    'relative': relative,
                    'level': level,
                    'value': reading,
                    'event': ', '.join(sensor['event'])
                })
