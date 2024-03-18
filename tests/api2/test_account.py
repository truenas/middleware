import os
import sys

import pytest

from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.utils import call, client
from middlewared.test.integration.utils.audit import expect_audit_method_calls

sys.path.append(os.getcwd())
from functions import DELETE, POST, PUT


@pytest.mark.parametrize("api", ["ws", "rest"])
def test_create_account_audit(api):
    user_id = None
    try:
        with expect_audit_method_calls([{
            "method": "user.create",
            "params": [
                {
                    "username": "sergey",
                    "full_name": "Sergey",
                    "group_create": True,
                    "home": "/nonexistent",
                    "password": "********",
                }
            ],
            "description": "Create user sergey",
        }]):
            payload = {
                "username": "sergey",
                "full_name": "Sergey",
                "group_create": True,
                "home": "/nonexistent",
                "password": "password",
            }
            if api == "ws":
                user_id = call("user.create", payload)
            elif api == "rest":
                result = POST(f"/user/", payload)
                assert result.status_code == 200, result.text
                user_id = result.json()
            else:
                raise ValueError(api)
    finally:
        if user_id is not None:
            call("user.delete", user_id)


@pytest.mark.parametrize("api", ["ws", "rest"])
def test_update_account_audit(api):
    with user({
        "username": "user2",
        "full_name": "user2",
        "group_create": True,
        "password": "test1234",
    }) as u:
        with expect_audit_method_calls([{
            "method": "user.update",
            "params": [u["id"], {}],
            "description": "Update user user2",
        }]):
            if api == "ws":
                call("user.update", u["id"], {})
            elif api == "rest":
                result = PUT(f"/user/id/{u['id']}", {})
                assert result.status_code == 200, result.text
            else:
                raise ValueError(api)


@pytest.mark.parametrize("api", ["ws", "rest"])
def test_delete_account_audit(api):
    with user({
        "username": "user2",
        "full_name": "user2",
        "group_create": True,
        "password": "test1234",
    }) as u:
        with expect_audit_method_calls([{
            "method": "user.delete",
            "params": [u["id"], {}],
            "description": "Delete user user2",
        }]):
            if api == "ws":
                call("user.delete", u["id"], {})
            elif api == "rest":
                result = DELETE(f"/user/id/{u['id']}")
                assert result.status_code == 200, result.text
            else:
                raise ValueError(api)


@pytest.mark.parametrize("api", ["ws", "rest"])
def test_create_group_audit(api):
    group_id = None
    try:
        with expect_audit_method_calls([{
            "method": "group.create",
            "params": [
                {
                    "name": "group2",
                }
            ],
            "description": "Create group group2",
        }]):
            payload = {
                "name": "group2",
            }
            if api == "ws":
                group_id = call("group.create", payload)
            elif api == "rest":
                result = POST(f"/group/", payload)
                assert result.status_code == 200, result.text
                group_id = result.json()
            else:
                raise ValueError(api)
    finally:
        if group_id is not None:
            call("group.delete", group_id)


@pytest.mark.parametrize("api", ["ws", "rest"])
def test_update_group_audit(api):
    with group({
        "name": "group2",
    }) as g:
        with expect_audit_method_calls([{
            "method": "group.update",
            "params": [g["id"], {}],
            "description": "Update group group2",
        }]):
            if api == "ws":
                call("group.update", g["id"], {})
            elif api == "rest":
                result = PUT(f"/group/id/{g['id']}", {})
                assert result.status_code == 200, result.text
            else:
                raise ValueError(api)


@pytest.mark.parametrize("api", ["ws", "rest"])
def test_delete_group_audit(api):
    with group({
        "name": "group2",
    }) as g:
        with expect_audit_method_calls([{
            "method": "group.delete",
            "params": [g["id"], {}],
            "description": "Delete group group2",
        }]):
            if api == "ws":
                call("group.delete", g["id"], {})
            elif api == "rest":
                result = DELETE(f"/group/id/{g['id']}")
                assert result.status_code == 200, result.text
            else:
                raise ValueError(api)


def test_update_account_using_api_key():
    with api_key([{"method": "CALL", "resource": "user.update"}]) as key:
        with client(auth=None) as c:
            assert c.call("auth.login_with_api_key", key)

            c.call("user.update", 1, {})


def test_update_account_using_token():
    token = call("auth.generate_token", 300)

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)

        c.call("user.update", 1, {})
