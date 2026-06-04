from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
    OneShotAlertClass,
)
from middlewared.alert.schedule import CrontabSchedule
from middlewared.utils import ProductType, security


@dataclass(kw_only=True)
class LocalAccountExpiringAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SECURITY,
        level=AlertLevel.NOTICE,
        title="Local User Accounts Must Change Password",
        text="The following local user accounts must change passwords : %(accounts)s",
    )

    accounts: str


@dataclass(kw_only=True)
class LocalAccountExpiredAlert(AlertClass):
    """
    One or more accounts are actually expired.
    """
    config = AlertClassConfig(
        category=AlertCategory.SECURITY,
        level=AlertLevel.WARNING,
        title="Local User Accounts Are Expired",
        text="The following local user accounts have expired: %(accounts)s",
    )

    accounts: str


class AllAdminAccountsExpiredAlert(OneShotAlertClass):
    """
    All local administrator accounts have expired passwords. This means we have
    potentially locked out ability to administer the NAS. To facilitate recovery
    we will disable password aging feature until some recovery effort is done.
    The most likely reason for this happening is that the user has restored a
    configuration backup with old passwords.
    """
    config = AlertClassConfig(
        category=AlertCategory.SECURITY,
        level=AlertLevel.CRITICAL,
        title="All local full administrator accounts are expired.",
        text=(
            "All administrator accounts with full administrator privilege are expired. "
            "In order to allow recovery, password expiration has been temporarily disabled for "
            "local administrator accounts with full admin privileges until at least one "
            "account password has been updated."
        ),
    )


class SecurityLocalUserAccountExpirationAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=0)
    run_on_backup_node = False
    products = (ProductType.ENTERPRISE,)

    async def check(self) -> list[Alert[Any]]:
        sec = await self.middleware.call("system.security.config")
        max_pw_age = sec["max_password_age"]
        if not max_pw_age:
            # password aging disabled and so we can skip these checks
            return []

        unlocked_local_accounts = await self.middleware.call("user.query", [
            ["local", "=", True],
            ["password_disabled", "=", False],
            ["unixhash", "!=", "*"],
            ["locked", "=", False]
        ])

        if not any(
            # Generate this alert an extra day early since we don't want to risk admin lockout
            "FULL_ADMIN" in acct["roles"] and acct["password_age"] < max_pw_age - 1
            for acct in unlocked_local_accounts
        ):
            # Once per day we check whether we've potentially locked out all
            # admins from accessing the NAS. If that occurs we forcibly regenerate
            # the shadow file, which will have the effect of disabling password aging
            # for accounts with FULL_ADMIN privilege (unlocking age-related lockout)
            # and generating a separate CRITICAL alert. The separate CRITICAL alert
            # will be automatically cleared on subsequent etc.generate shadow after
            # updating password.
            await self.middleware.call('etc.generate', 'shadow')

        alerts: list[Alert[Any]] = []

        # Alert for expiring accounts
        expiring_accounts = ", ".join(
            acct["username"]
            for acct in unlocked_local_accounts
            if max_pw_age - security.PASSWORD_PROMPT_AGE <= acct["password_age"] < max_pw_age
        )
        if expiring_accounts:
            alerts.append(Alert(LocalAccountExpiringAlert(accounts=expiring_accounts)))

        # Alert for expired accounts
        expired_accounts = ", ".join(
            acct["username"]
            for acct in unlocked_local_accounts
            if acct["password_age"] >= max_pw_age
        )
        if expired_accounts:
            alerts.append(Alert(LocalAccountExpiredAlert(accounts=expired_accounts)))

        return alerts
