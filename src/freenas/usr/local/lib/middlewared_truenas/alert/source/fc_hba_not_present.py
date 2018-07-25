# Copyright (c) 2018 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import subprocess

from lxml import etree

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource


class FCHBANotPresentAlertSource(ThreadedAlertSource):
    level = AlertLevel.CRITICAL
    title = "FC HBA not present"

    def check_sync(self):
        portlist = etree.fromstring(subprocess.check_output(["ctladm", "portlist", "-x"], encoding="utf-8"))
        alerts = []
        for channeltotarget in self.middleware.call_sync("datastore.query", "services.fibrechanneltotarget"):
            if not portlist.xpath(f"//port_name[text()='{channeltotarget['fc_port']}']"):
                alerts.append(Alert(
                    title="HBA for FC port %(port)s configured for target %(target)r is not present",
                    args={
                        "port": channeltotarget["fc_port"],
                        "target": channeltotarget["fc_target"]["iscsi_target_name"],
                    }
                ))
        return alerts
