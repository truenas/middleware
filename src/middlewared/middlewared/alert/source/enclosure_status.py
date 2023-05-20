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

    bad_elements = []

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
        good_enclosures = []
        bad_elements = []
        for enc in await self.middleware.call('enclosure.query'):
            good_enclosures.append([enc['number'], enc['name']])

            for element_values in enc['elements']:
                for value in element_values['elements']:
                    if await self.should_report(enc, value):
                        args = [
                            enc['number'],
                            enc['name'],
                            value['descriptor'],
                            value['slot'],
                            hex(value['slot']),
                            value['status']
                        ]
                        for i, (another_args, count) in enumerate(self.bad_elements):
                            if another_args == args:
                                bad_elements.append((args, count + 1))
                                break
                        else:
                            bad_elements.append((args, 1))

        self.bad_elements = bad_elements

        alerts = []
        for args, count in bad_elements:
            # We only report unhealthy enclosure elements if they were unhealthy 5 probes in a row (1 probe = 1 minute)
            if count >= 5:
                try:
                    good_enclosures.remove(args[:2])
                except ValueError:
                    pass

                alerts.append(Alert(EnclosureUnhealthyAlertClass, args=args))

        for args in good_enclosures:
            alerts.append(Alert(EnclosureHealthyAlertClass, args=args))

        return alerts
