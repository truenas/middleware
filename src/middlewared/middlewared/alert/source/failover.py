import errno

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource, UnavailableException
from middlewared.service_exception import CallError


class FailoverInterfaceNotFoundAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Failover Internal Interface Not Found"
    text = "Failover internal interface not found. Contact support."

    products = ("ENTERPRISE",)


class TrueNASVersionsMismatchAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "TrueNAS Versions Mismatch In Failover"
    text = "TrueNAS versions mismatch in failover. Update both controllers to the same version."

    products = ("ENTERPRISE",)


class FailoverAccessDeniedAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Failover Access Denied"
    text = "Failover access denied. Please reconfigure it."

    products = ("ENTERPRISE",)


class FailoverStatusCheckFailedAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Failed to Check Failover Status with the Other Controller"
    text = "Failed to check failover status with the other controller: %s."

    products = ("ENTERPRISE",)


class FailoverFailedAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Failover Failed"
    text = "Failover failed: %s."
    products = ("SCALE_ENTERPRISE",)


class VRRPStatesDoNotAgreeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Controllers VRRP States Do Not Agree"
    text = "Controllers VRRP states do not agree: %(error)s."
    products = ("SCALE_ENTERPRISE",)


class FailoverAlertSource(ThreadedAlertSource):
    products = ("ENTERPRISE",)
    failover_related = True
    run_on_backup_node = False

    def check_sync(self):
        if not self.middleware.call_sync('failover.licensed'):
            return []
        elif not self.middleware.call_sync('failover.internal_interfaces'):
            return [Alert(FailoverInterfaceNotFoundAlertClass)]

        alerts = []
        try:
            if not self.middleware.call_sync('failover.call_remote', 'system.ready'):
                raise UnavailableException()

            local_version = self.middleware.call_sync('system.version')
            remote_version = self.middleware.call_sync('failover.call_remote', 'system.version')
            if local_version != remote_version:
                return [Alert(TrueNASVersionsMismatchAlertClass)]

            local = self.middleware.call_sync('failover.vip.get_states')
            remote = self.middleware.call_sync('failover.call_remote', 'failover.vip.get_states')
            if err := self.middleware.call_sync('failover.vip.check_states', local, remote):
                return [Alert(VRRPStatesDoNotAgreeAlertClass, {"error": i}) for i in err]
        except CallError as e:
            if e.errno != errno.ECONNREFUSED:
                return [Alert(FailoverStatusCheckFailedAlertClass, [str(e)])]

        status = self.middleware.call_sync('failover.status')
        if status in ('ERROR', 'UNKNOWN'):
            return [Alert(FailoverFailedAlertClass, ['Check /root/syslog/failover.log on both controllers.'])]

        return []
