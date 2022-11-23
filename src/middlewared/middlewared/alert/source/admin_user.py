from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource, IntervalSchedule
from middlewared.plugins.account import ADMIN_UID
from middlewared.service_exception import MatchNotFound


class AdminUserIsOverriddenAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Admin User Is Overridden"
    text = "NSS query results are different for the locally set up `admin` user."


class AdminUserAlertSource(AlertSource):
    """
    There are ways (unsupported) via auxiliary parameters that users can intentionally enable mappings for LDAP and AD
    that go below UID 1000.
    """

    schedule = IntervalSchedule(timedelta(hours=24))

    async def check(self):
        try:
            admin = await self.middleware.call(
                "datastore.query",
                "account.bsdusers",
                [
                    ["uid", "=", ADMIN_UID],
                    ["username", "=", "admin"],
                    ["home", "=", "/home/admin"],
                ],
                {"get": True, "prefix": "bsdusr_"}
            )
        except MatchNotFound:
            return

        user_obj = await self.middleware.call("user.get_user_obj", {"uid": ADMIN_UID})

        if (
                (user_obj["pw_name"] != admin["username"]) or
                (user_obj["pw_gid"] != admin["group"]["bsdgrp_gid"]) or
                (user_obj["pw_gecos"] != admin["full_name"]) or
                (user_obj["pw_dir"] != admin["home"])
        ):
            return Alert(AdminUserIsOverriddenAlertClass)
