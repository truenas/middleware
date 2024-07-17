import logging

from datetime import timedelta
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource, SimpleOneShotAlertClass
from middlewared.alert.schedule import IntervalSchedule
from middlewared.plugins.directoryservices import DSStatus, DSType
from middlewared.utils.directoryservices.health import DSHealthObj, IPAHealthError, KRB5HealthError

log = logging.getLogger("ipa_check_alertmod")


class IPADomainBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "IPA Domain Connection Is Not Healthy"
    text = "%(err)s."


class IPADomainBindAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))
    run_on_backup_node = False

    async def check(self):
        if DSHealthObj.dstype is not DSType.IPA:
            return

        if DSHealthObj.status in (DSStatus.JOINING, DSStatus.LEAVING):
            return

        try:
            await self.middleware.call('directoryservices.health.check')
        except (KRB5HealthError, IPAHealthError):
            # this is potentially recoverable
            try:
                await self.middleware.call('directoryservices.health.recover')
            except Exception as e:
                # Recovery failed, generate an alert
                return Alert(
                    IPADomainBindAlertClass,
                    {'err': str(e)},
                    key=None
                )
        except Exception:
            # We shouldn't be raising other sorts of errors
            self.logger.error("Unexpected error while performing health check.", exc_info=True)


class IPALegacyConfigurationAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "IPA domain configuration is using LDAP compatibility"
    text = (
        "Attempt to fully join IPA domain failed. TrueNAS will continue to act as "
        "an IPA client but with diminished capabilities including lack of support "
        "for kerberos security for NFS and SMB protocols. %(errmsg)s"
    )

    async def delete(self, alerts, query):
        return []
