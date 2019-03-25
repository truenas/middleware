import subprocess

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource


class SmartdAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "smartd Is Not Running"
    text = "smartd is not running."


class SmartdAlertSource(ThreadedAlertSource):
    def check_sync(self):
        if self.middleware.call_sync("datastore.query", "services.services", [("srv_service", "=", "smartd"),
                                                                              ("srv_enable", "=", True)]):
            # sysctl kern.vm_guest will return a hypervisor name, or the string "none"
            # if FreeNAS is running on bare iron.
            p0 = subprocess.Popen(["/sbin/sysctl", "-n", "kern.vm_guest"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, encoding="utf8")
            status = p0.communicate()[0].strip()
            # This really isn"t confused with python None
            if status != "none":
                # We got something other than "none", maybe "vmware", "xen", "vbox".  Regardless, smartd not running
                # in these environments isn"t a huge deal.  So we"ll skip alerting.
                return

            if not self.middleware.call_sync("system.is_freenas"):
                if self.middleware.call_sync("failover.status") != "MASTER":
                    return

            if not self.middleware.call_sync("service.started", "smartd"):
                return Alert(SmartdAlertClass)
