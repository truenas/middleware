from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class EnclosureUnhealthyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Enclosure Status Is Not Healthy"
    text = "Enclosure /dev/ses%d (%s): %s at slot %s (in hex %s) is reporting %s."

    products = ("ENTERPRISE",)


class EnclosureHealthyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.INFO
    title = "Enclosure Status Is Healthy"
    text = "Enclosure /dev/ses%d (%s): is healthy."

    products = ("ENTERPRISE",)


class EnclosureStatusAlertSource(AlertSource):
    products = ("ENTERPRISE",)
    failover_related = True
    run_on_backup_node = False
    bad = ('Critical', 'Noncritical', 'Unknown', 'Unrecoverable')

    async def check(self):
        alerts = []

        for enc in await self.middleware.call('enclosure.query'):
            if enc.get('status') == 'OK':
                # m/x/z series devices return an overall status for the enclosure.
                # In the situations where it's OK, just move on.
                alerts.append(Alert(EnclosureHealthyAlertClass, args=[enc['number'], enc['name']]))
            else:
                for element_type, element_values in enc['elements'].items():
                    for slot, value in element_values.items():
                        if value['status'] in self.bad:
                            if enc['name'] == 'ECStream 3U16+4R-4X6G.3 d10c' and value['descriptor'] == '1.8V Sensor':
                                # The 1.8V sensor is bugged on the echostream enclosure (Z-series).
                                # The management chip loses it's mind and claims undervoltage, but
                                # scoping this confirms the voltage is fine.
                                # Ignore alerts from this element. Redmine # 10077
                                continue

                            # getting here means that we came across an element that isn't reporting
                            # a status we expect AND the overall enclosure status isn't "OK"
                            # (or isn't reported at all)
                            alerts.append(Alert(EnclosureUnhealthyAlertClass, args=[
                                enc['number'],
                                enc['name'],
                                value['descriptor'],
                                slot,
                                hex(slot),
                                value['value']
                            ]))

        return alerts
