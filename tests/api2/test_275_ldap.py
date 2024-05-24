#!/usr/bin/env python3

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

from middlewared.test.integration.assets.directory_service import ldap
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.assets.product import product_type
from middlewared.test.integration.utils import call, client

try:
    from config import (
        LDAPUSER,
        LDAPPASSWORD
    )
except ImportError:
    Reason = 'LDAP* variable are not setup in config.py'
    pytestmark = pytest.mark.skipif(True, reason=Reason)


@pytest.fixture(scope="module")
def do_ldap_connection(request):
    with ldap() as ldap_conn:
        with product_type():
            yield (request, ldap_conn)


def test_verify_default_ldap_state_is_disabled():
    assert call('directoryservices.status')['type'] is None


def test_setup_and_enabling_ldap(do_ldap_connection):
    ds = call('directoryservices.status')
    assert ds['type'] == 'LDAP'
    assert ds['status'] == 'HEALTHY'

    # This forces an additional health check
    alerts = call('alert.run_source', 'LDAPBind')
    assert alerts == [], str(alerts)


def test_verify_ldap_enable_is_true(do_ldap_connection):
    ldap = call('ldap.config')
    assert ldap['enable'] is True
    assert ldap['server_type'] == 'OPENLDAP'


def test_account_privilege_authentication(do_ldap_connection):
    call("system.general.update", {"ds_auth": True})
    try:
        gid = call("user.get_user_obj", {"username": LDAPUSER})["pw_gid"]
        with privilege({
            "name": "LDAP privilege",
            "local_groups": [],
            "ds_groups": [gid],
            "allowlist": [{"method": "CALL", "resource": "system.info"}],
            "web_shell": False,
        }):
            with client(auth=(LDAPUSER, LDAPPASSWORD)) as c:
                methods = c.call("core.get_methods")

            assert "system.info" in methods
            assert "pool.create" not in methods
    finally:
        call("system.general.update", {"ds_auth": False})


def test_check_ldap_user(do_ldap_connection):
    """
    get_user_obj is a wrapper around the pwd module.
    This check verifies that the user is _actually_ created.
    """
    call('user.get_user_obj', {"username": LDAPUSER})
