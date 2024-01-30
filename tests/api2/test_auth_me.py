import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.utils import call, client

pytestmark = pytest.mark.rbac


def test_works():
    user = call("auth.me")

    assert user["pw_uid"] == 0
    assert user["pw_name"] == "root"
    assert user['two_factor_config'] is not None
    assert user['privilege']['webui_access']


def test_works_for_token():
    token = call("auth.generate_token", 300)

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)

        user = c.call("auth.me")

        assert user["pw_uid"] == 0
        assert user["pw_name"] == "root"
        assert user['two_factor_config'] is not None
        assert 'SYS_ADMIN' in user['account_attributes']
        assert 'LOCAL' in user['account_attributes']


def test_does_not_work_for_api_key():
    with api_key([{"method": "CALL", "resource": "auth.me"}]) as key:
        with client(auth=None) as c:
            assert c.call("auth.login_with_api_key", key)

            with pytest.raises(CallError) as ve:
                c.call("auth.me")

            assert ve.value.errmsg == "You are logged in using API_KEY"


def test_attributes():
    user = call("auth.me")
    assert "test" not in user["attributes"]

    call("auth.set_attribute", "test", "value")

    user = call("auth.me")
    assert user["attributes"]["test"] == "value"

    call("auth.set_attribute", "test", "new_value")

    user = call("auth.me")
    assert user["attributes"]["test"] == "new_value"


def test_distinguishes_attributes():
    builtin_administrators_group_id = call(
        "datastore.query",
        "account.bsdgroups",
        [["group", "=", "builtin_administrators"]],
        {"get": True, "prefix": "bsdgrp_"},
    )["id"]

    with user({
        "username": "admin",
        "full_name": "Admin",
        "group_create": True,
        "groups": [builtin_administrators_group_id],
        "home": f"/nonexistent",
        "password": "test1234",
    }) as admin:
        with client(auth=("admin", "test1234")) as c:
            me = c.call("auth.me")
            assert "test" not in me["attributes"]

            c.call("auth.set_attribute", "test", "value")

            me = c.call("auth.me")
            assert me["attributes"]["test"] == "value"

            c.call("auth.set_attribute", "test", "new_value")

            me = c.call("auth.me")
            assert me["attributes"]["test"] == "new_value"
            assert me['two_factor_config'] is not None
            assert 'SYS_ADMIN' not in me['account_attributes']
            assert 'LOCAL' in me['account_attributes']
            assert me['privilege']['webui_access']

    assert not call("datastore.query", "account.bsdusers_webui_attribute", [["uid", "=", admin["uid"]]])
