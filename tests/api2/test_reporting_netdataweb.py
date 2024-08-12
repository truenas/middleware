import pytest
import requests
from requests.auth import HTTPBasicAuth

from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call, url


def test_netdata_web_login_succeed():
    password = call('reporting.netdataweb_generate_password')
    r = requests.get(f'{url()}/netdata/', auth=HTTPBasicAuth('root', password))
    assert r.status_code == 200


def test_netdata_web_login_fail():
    r = requests.get(f'{url()}/netdata/')
    assert r.status_code == 401


@pytest.mark.parametrize("role,expected",  [
    (["FULL_ADMIN"], True),
    (["READONLY_ADMIN"], True),
])
def test_netdata_web_login_unprivileged_succeed(role, expected):
    with unprivileged_user_client(roles=role) as c:
        me = c.call('auth.me')
        password = c.call('reporting.netdataweb_generate_password')
        r = requests.get(f'{url()}/netdata/', auth=HTTPBasicAuth(me['pw_name'], password))
        assert (r.status_code == 200) is expected
