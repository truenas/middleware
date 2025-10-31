from middlewared.alert.base import Alert, AlertClass, AlertSource, SimpleOneShotAlertClass, AlertCategory, AlertLevel
from middlewared.alert.schedule import CrontabSchedule
from middlewared.utils import ProductType, security
from middlewared.utils.filter_list import filter_list


class LocalAccountExpiringAlertClass(AlertClass):
    category = AlertCategory.SECURITY
    level = AlertLevel.NOTICE
    title = "Local User Accounts Must Change Password"
    text = "The following local user accounts must change passwords : %(accounts)s"


class LocalAccountExpiredAlertClass(AlertClass):
    """
    One or more accounts are actually expired.
    """
    category = AlertCategory.SECURITY
    level = AlertLevel.WARNING
    title = "Local User Accounts Are Expired"
    text = "The following local user accounts have expired: %(accounts)s"


class AllAdminAccountsExpiredAlertClass(AlertClass, SimpleOneShotAlertClass):
    """
    All local administrator accounts have expired passwords. This means we have
    potentially locked out ability to administer the NAS. To facilitate recovery
    we will disable password aging feature until some recovery effort is done.
    The most likely reason for this happening is that the user has restored a
    configuration backup with old passwords.
    """
    category = AlertCategory.SECURITY
    level = AlertLevel.CRITICAL
    title = "All local full administrator accounts are expired."
    text = (
        "All administrator accounts with full administrator privilege are expired. "
        "In order to allow recovery, password expiration has been temporarily disabled for "
        "local administrator accounts with full admin privileges until at least one "
        "account password has been updated."
    )


class SecurityLocalUserAccountExpirationAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=0)
    run_on_backup_node = False
    products = (ProductType.ENTERPRISE,)

    async def check(self):
        alerts = []
        sec = await self.middleware.call("system.security.config")
        if not sec["max_password_age"]:
            # password aging disabled and so we can skip these checks
            return alerts

        unlocked_local_accounts = await self.middleware.call("user.query", [
            ["local", "=", True],
            ["password_disabled", "=", False],
            ["unixhash", "!=", "*"],
            ["locked", "=", False]
        ])

        expiring = filter_list(unlocked_local_accounts, [
            ["password_age", ">=", sec["max_password_age"] - security.PASSWORD_PROMPT_AGE],
            ["password_age", "<", sec["max_password_age"]],
        ])

        expired = filter_list(unlocked_local_accounts, [
            ["password_age", ">=", sec["max_password_age"]]
        ])

        # Generate this alert an extra day early since we don't want to risk admin lockout
        active_full_admins = filter_list(unlocked_local_accounts, [
            ["roles", "rin", "FULL_ADMIN"],
            ["password_age", "<", sec["max_password_age"] - 1],
        ])

        if not active_full_admins:
            # Once per day we check whether we've potentially locked out all
            # admins from accessing the NAS. If that occurs we forcibly regenerate
            # the shadow file, which will have the effect of disabling password aging
            # for accounts with FULL_ADMIN privilege (unlocking age-related lockout)
            # and generating a separate CRITICAL alert. The separate CRITICAL alert
            # will be automatically cleared on subsequent etc.generate shadow after
            # updating password.
            await self.middleware.call('etc.generate', 'shadow')

        if expiring:
            alerts.append(Alert(
                LocalAccountExpiringAlertClass,
                {"accounts": ", ".join([u["username"] for u in expiring])}
            ))

        if expired:
            alerts.append(Alert(
                LocalAccountExpiredAlertClass,
                {"accounts": ", ".join([u["username"] for u in expired])}
            ))

        return alerts
