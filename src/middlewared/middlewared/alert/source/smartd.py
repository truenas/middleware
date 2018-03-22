import subprocess

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource


class smartdAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "smartd not running"

    def check_sync(self):
        if self.middleware.call_sync("datastore.query", "services.services", [("srv_service", "=", "smartd"),
                                                                              ("srv_enable", "=", True)]):
            # sysctl kern.vm_guest will return a hypervisor name, or the string "none"
            # if FreeNAS is running on bare iron.
            p0 = subprocess.Popen(["/sbin/sysctl",  "-n",  "kern.vm_guest"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, encoding="utf8")
            status = p0.communicate()[0].strip()
            # This really isn"t confused with python None
            if status != "none":
                # We got something other than "none", maybe "vmware", "xen", "vbox".  Regardless, smartd not running
                # in these environments isn"t a huge deal.  So we"ll skip alerting.
                return
            try:
                if self.middleware.call_sync("notifier.failover_status") != "MASTER":
                    return
            except Exception:
                return
            p1 = subprocess.Popen(["/usr/sbin/service", "smartd", "status"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, encoding="utf8")
            status = p1.communicate()[0]
            if p1.returncode == 1:
                return Alert(status)
