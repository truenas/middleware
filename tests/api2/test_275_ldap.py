import pytest

from middlewared.test.integration.assets.directory_service import ldap, LDAPUSER, LDAPPASSWORD
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.assets.product import product_type
from middlewared.test.integration.utils import call, client

pytestmark = [
    pytest.mark.skipif(not LDAPUSER, reason='Missing LDAP configuration'),
]


@pytest.fixture(scope="module")
def do_ldap_connection(request):
    with ldap() as ldap_conn:
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
        group = call("user.get_user_obj", {"username": LDAPUSER})
        assert group["source"] == "LDAP"
        with privilege({
            "name": "LDAP privilege",
            "local_groups": [],
            "ds_groups": [group["pw_gid"]],
            "allowlist": [{"method": "CALL", "resource": "system.info"}],
            "web_shell": False,
        }):
            with client(auth=(LDAPUSER, LDAPPASSWORD)) as c:
                methods = c.call("core.get_methods")

            assert "system.info" in methods
            assert "pool.create" not in methods
    finally:
        call("system.general.update", {"ds_auth": False})
