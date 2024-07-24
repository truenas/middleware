import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call, client
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset


def test_root_password_disabled():
    with client() as c:
        root_user_id = c.call(
            "datastore.query",
            "account.bsdusers",
            [["username", "=", "root"]],
            {"get": True, "prefix": "bsdusr_"},
        )["id"]

        c.call("datastore.update", "account.bsdusers", root_user_id, {"bsdusr_password_disabled": True})
        c.call("etc.generate", "user")
        try:
            alerts = c.call("alert.list")
            assert any(alert["klass"] == "WebUiRootLogin" for alert in alerts), alerts

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
                }, get_instance=False):
                    alerts = c.call("alert.list")
                    assert not any(alert["klass"] == "WebUiRootLogin" for alert in alerts), alerts

                    # Root should not be able to log in with password anymore
                    with pytest.raises(CallError):
                        call("system.info", client_kwargs=dict(auth_required=False))

                    assert events[0][1]["fields"]["usernames"] == ["admin"]

                    c.call("datastore.update", "account.bsdusers", root_user_id, {"bsdusr_password_disabled": False})
                    c.call("etc.generate", "user")
        finally:
            # In case of a failure
            c.call("datastore.update", "account.bsdusers", root_user_id, {"bsdusr_password_disabled": False})
            c.call("etc.generate", "user")
