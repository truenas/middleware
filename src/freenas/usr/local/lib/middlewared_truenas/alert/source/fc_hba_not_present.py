import subprocess
from xml.etree import ElementTree as ET

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource


class FCHBANotPresentAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "FC HBA Is not Present"
    text = "HBA for FC port %(port)s configured for target %(target)r is not present."

    products = ("ENTERPRISE",)


class FCHBANotPresentAlertSource(ThreadedAlertSource):
    products = ("ENTERPRISE",)

    def check_sync(self):
        ports = set()
        xml = subprocess.check_output(["ctladm", "portlist", "-x"], encoding="utf-8")
        for port in ET.fromstring(xml).findall(".//*[frontend_type='camtgt']"):
            ports.add((
                port.find("./port_name").text,
                port.find("./physical_port").text,
                port.find("./virtual_port").text
            ))

        alerts = []
        for channeltotarget in self.middleware.call_sync("datastore.query", "services.fibrechanneltotarget"):
            fq_fc_port = channeltotarget["fc_port"]
            if fq_fc_port.count("/") == 0:
                fq_fc_port += "/0"
            if fq_fc_port.count("/") == 1:
                fq_fc_port += "/0"
            port_name, physical_port, virtual_port = fq_fc_port.split("/", 2)
            if (port_name, physical_port, virtual_port) not in ports:
                alerts.append(Alert(
                    FCHBANotPresentAlertClass,
                    {
                        "port": channeltotarget["fc_port"],
                        "target": channeltotarget["fc_target"]["iscsi_target_name"],
                    }
                ))

        return alerts
