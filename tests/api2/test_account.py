from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.utils import call, client


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
