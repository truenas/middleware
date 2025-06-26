import pytest

from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.assets.product import product_type
from middlewared.test.integration.utils import call, client


@pytest.fixture(scope="module")
def do_ldap_connection(request):
    with directoryservice('LDAP') as ldap_conn:
        with product_type():
            yield ldap_conn


def test_ldap_initial_state():
    ds = call("directoryservices.status")
    assert ds["type"] is None
    assert ds["status"] is None

    ldap_config = call("ldap.config")
    assert not ldap_config["enable"]


def test_ldap_schema_choices():
    expected = {"RFC2307", "RFC2307BIS"}

    choices = call("ldap.schema_choices")
    assert set(choices) == expected


def test_get_ldap_ssl_choices():
    expected = {"OFF", "ON", "START_TLS"}

    choices = call("ldap.ssl_choices")
    assert set(choices) == expected


def test_ldap_connection(do_ldap_connection):
    ds = call("directoryservices.status")
    assert ds["type"] == "LDAP"
    assert ds["status"] == "HEALTHY"

    ldap_config = call("ldap.config")
    assert ldap_config["enable"]
    assert ldap_config["server_type"] == "OPENLDAP"


def test_ldap_user_group_cache(do_ldap_connection):
    assert call("user.query", [["local", "=", False]], {'count': True}) != 0
    assert call("group.query", [["local", "=", False]], {'count': True}) != 0


def test_account_privilege_authentication(do_ldap_connection):

    call("system.general.update", {"ds_auth": True})
    try:
        account = do_ldap_connection["account"]
        call("directoryservices.health.check")

        group = call("group.query", [["gid", "=", account.user_obj["pw_gid"]]])
        assert group, f'{account.user_obj["pw_gid"]}: lookup of group id failed'
        assert group[0]["local"] is False
        with privilege({
            "name": "LDAP privilege",
            "local_groups": [],
            "ds_groups": [group[0]["gid"]],
            "roles": ["READONLY_ADMIN"],
            "web_shell": False,
        }):
            with client(auth=(account.username, account.password)) as c:
                methods = c.call("core.get_methods")
                me = c.call("auth.me")

            assert "system.info" in methods
            assert "pool.create" not in methods
            assert "DIRECTORY_SERVICE" in me['account_attributes']
            assert "LDAP" in me['account_attributes']

    finally:
        call("system.general.update", {"ds_auth": False})
