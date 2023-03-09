from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class EnclosureUnhealthyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Enclosure Status Is Not Healthy"
    text = "Enclosure (%s): Element \"%s\" is reporting a status of \"%s\" with a value of \"%s\". (raw value \"%s\")"
    products = ("SCALE_ENTERPRISE",)


class EnclosureHealthyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.INFO
    title = "Enclosure Status Is Healthy"
    text = "Enclosure (%s) is healthy."
    products = ("SCALE_ENTERPRISE",)


class EnclosureStatusAlertSource(AlertSource):
    products = ("SCALE_ENTERPRISE",)
    failover_related = True
    run_on_backup_node = False
    bad = ('critical', 'noncritical', 'unknown', 'unrecoverable', 'not installed')

    async def should_report(self, enclosure, element):
        should_report = True
        if element['status'].lower() in self.bad and element['value'] != 'None':
            if element['name'] == 'Enclosure':
                # this is an element that provides an "overview" for all the other elements
                # i.e. if a power supply element is reporting critical, this will (should)
                # report critical as well. Sometimes, however, this will constantly report
                # a bad status, just ignore it #11918
                should_report = False
            elif enclosure['name'] == 'ECStream 3U16+4R-4X6G.3 d10c' and element['descriptor'] == '1.8V Sensor':
                # The 1.8V sensor is bugged on the echostream enclosure (Z-series). The
                # management chip loses it's mind and claims undervoltage, but scoping
                # this confirms the voltage is fine. Ignore alerts from this element. #10077
                should_report = False
        else:
            should_report = False

        return should_report

    async def check(self):
        alerts = []
        for enc in await self.middleware.call('enclosure.query'):
            healthy = True
            for ele in sum([e['elements'] for e in enc['elements']], []):
                if await self.should_report(enc, ele):
                    healthy = False
                    alerts.append(Alert(EnclosureUnhealthyAlertClass, args=[
                        enc['name'],
                        ele['name'],
                        ele['status'],
                        ele['value'],
                        ele['value_raw'],
                    ]))

            if healthy:
                # we've iterated all elements of a given enclosure and nothing
                # was reported as unhealthy
                alerts.append(Alert(EnclosureHealthyAlertClass, args=[enc['name']]))

        return alerts
