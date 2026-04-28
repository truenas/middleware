from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
    IntervalSchedule,
)
from middlewared.plugins.account_.constants import ADMIN_UID
from middlewared.service_exception import MatchNotFound


@dataclass(kw_only=True)
class AdminUserIsOverriddenAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Admin User Is Overridden",
        text="NSS query results are different for the locally set up `%(username)s` user.",
    )

    username: str


class AdminUserAlertSource(AlertSource):
    """
    There are ways (unsupported) via auxiliary parameters that users can intentionally enable mappings for LDAP and AD
    that go below UID 1000.
    """

    schedule = IntervalSchedule(timedelta(hours=24))

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        try:
            admin = await self.middleware.call(
                "datastore.query",
                "account.bsdusers",
                [
                    ["uid", "=", ADMIN_UID],
                ],
                {"get": True, "prefix": "bsdusr_"}
            )
        except MatchNotFound:
            return None

        user_obj = await self.middleware.call("user.get_user_obj", {"uid": ADMIN_UID})

        if (
                (user_obj["pw_name"] != admin["username"]) or
                (user_obj["pw_gid"] != admin["group"]["bsdgrp_gid"]) or
                (user_obj["pw_gecos"] != admin["full_name"]) or
                (user_obj["pw_dir"] != admin["home"])
        ):
            return Alert(AdminUserIsOverriddenAlert(username=admin["username"]))

        return None
