from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource, ProductType
from middlewared.alert.schedule import IntervalSchedule


class FIPSMisconfigurationAlertClass(AlertClass):
    category = AlertCategory.SECURITY
    level = AlertLevel.CRITICAL
    title = "FIPS misconfiguration"
    text = "FIPS is %(configuration)s, but FIPS provider is %(state)s."


class FIPSProviderAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))

    products = (ProductType.ENTERPRISE,)
    run_on_backup_node = False

    async def check(self):
        fips_configured = (await self.middleware.call('system.security.config'))['enable_fips']
        fips_enabled = await self.middleware.call('system.security.info.fips_enabled')

        if fips_configured and not fips_enabled:
            return Alert(FIPSMisconfigurationAlertClass, {"configuration": "enabled", "state": "not active"})

        if not fips_configured and fips_enabled:
            return Alert(FIPSMisconfigurationAlertClass, {"configuration": "disabled", "state": "active"})
