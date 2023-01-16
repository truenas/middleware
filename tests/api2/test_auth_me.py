import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.utils import call, client


def test_works():
    user = call("auth.me")

    assert user["pw_uid"] == 0
    assert user["pw_name"] == "root"


def test_works_for_token():
    token = call("auth.generate_token", 300)

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)

        user = c.call("auth.me")

        assert user["pw_uid"] == 0
        assert user["pw_name"] == "root"


def test_does_not_work_for_api_key():
    with api_key([{"method": "CALL", "resource": "auth.me"}]) as key:
        with client(auth=None) as c:
            assert c.call("auth.login_with_api_key", key)

            with pytest.raises(CallError) as ve:
                c.call("auth.me")

            assert ve.value.errmsg == "You are logged in using API_KEY"
