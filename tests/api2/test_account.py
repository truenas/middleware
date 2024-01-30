import os
import sys

import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.utils import call, client
from middlewared.test.integration.utils.audit import expect_audit_method_calls

sys.path.append(os.getcwd())
from functions import PUT

pytestmark = pytest.mark.audit


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
