import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call, client
from middlewared.test.integration.utils.alert import (
    get_alerts_by_class,
    wait_for_alerts_by_class,
    wait_for_alerts_by_class_cleared,
)
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset

ALERT_CLASS = "WebUiRootLogin"


def set_root_password_disabled(c, root_user_id, disabled):
    c.call("datastore.update", "account.bsdusers", root_user_id, {"bsdusr_password_disabled": disabled})
    c.call("etc.generate", "user")


def test_root_password_disabled():
    with client() as c:
        root_user_id = c.call(
            "datastore.query",
            "account.bsdusers",
            [["username", "=", "root"]],
            {"get": True, "prefix": "bsdusr_"},
        )["id"]

        set_root_password_disabled(c, root_user_id, True)
        try:
            assert wait_for_alerts_by_class(ALERT_CLASS), call("alert.list")

            builtin_administrators_group_id = c.call(
                "datastore.query",
                "account.bsdgroups",
                [["group", "=", "builtin_administrators"]],
                {"get": True, "prefix": "bsdgrp_"},
            )["id"]

            with dataset(f"admin_homedir") as homedir:
                events = []

                def callback(type, **message):
                    events.append((type, message))

                c.subscribe("user.web_ui_login_disabled", callback, sync=True)

                with user({
                    "username": "admin",
                    "full_name": "Admin",
                    "group_create": True,
                    "groups": [builtin_administrators_group_id],
                    "home": f"/mnt/{homedir}",
                    "password": "test1234",
                }):
                    try:
                        assert wait_for_alerts_by_class_cleared(ALERT_CLASS), get_alerts_by_class(ALERT_CLASS)

                        # Root should not be able to log in with password anymore
                        with pytest.raises(CallError):
                            call("system.info", client_kwargs=dict(auth_required=False))

                        assert events[0][1]["fields"]["usernames"] == ["admin"]
                    finally:
                        # `user.delete` refuses to remove the last local administrator, so root has to
                        # regain its password before the `admin` user goes away.
                        set_root_password_disabled(c, root_user_id, False)
        finally:
            # In case of a failure
            set_root_password_disabled(c, root_user_id, False)
