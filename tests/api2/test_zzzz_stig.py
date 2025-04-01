import pytest

from middlewared.service_exception import ValidationErrors as Verr
from middlewared.test.integration.assets.product import product_type, set_fips_available
from middlewared.test.integration.assets.two_factor_auth import (
    enabled_twofactor_auth, get_user_secret, get_2fa_totp_token
)
from middlewared.test.integration.utils import call, client, password
from truenas_api_client import ValidationErrors


def get_excluded_admins():
    """ Return the list of immutable admins with passwords enabled """
    return [
        user["id"] for user in call(
            'user.query', [
                ["immutable", "=", True], ["password_disabled", "=", False],
                ["locked", "=", False], ["unixhash", "!=", "*"]
            ],
        )
    ]


@pytest.fixture(autouse=True)
def clear_ratelimit():
    call('rate.limit.cache_clear')


@pytest.fixture(scope='function')
def enterprise_product():
    with product_type('ENTERPRISE'):
        with set_fips_available(True):
            yield


@pytest.fixture(scope='function')
def community_product():
    with product_type('COMMUNITY_EDITION'):
        with set_fips_available(False):
            yield


@pytest.fixture(scope='module')
def two_factor_enabled():
    with enabled_twofactor_auth(ssh=True) as two_factor_config:
        yield two_factor_config


@pytest.fixture(scope='module')
def two_factor_non_admin(two_factor_enabled, unprivileged_user_fixture):
    privilege = call('privilege.query', [['local_groups.0.group', '=', unprivileged_user_fixture.group_name]])
    assert len(privilege) > 0, 'Privilege not found'
    call('privilege.update', privilege[0]['id'], {'roles': ['SHARING_ADMIN']})

    try:
        call('user.renew_2fa_secret', unprivileged_user_fixture.username, {'interval': 60})
        user_obj_id = call('user.query', [['username', '=', unprivileged_user_fixture.username]], {'get': True})['id']
        secret = get_user_secret(user_obj_id)
        yield (unprivileged_user_fixture, secret)
    finally:
        call('privilege.update', privilege[0]['id'], {'roles': []})


@pytest.fixture(scope='module')
def two_factor_full_admin(two_factor_enabled, unprivileged_user_fixture):
    privilege = call('privilege.query', [['local_groups.0.group', '=', unprivileged_user_fixture.group_name]])
    assert len(privilege) > 0, 'Privilege not found'
    call('privilege.update', privilege[0]['id'], {'roles': ['FULL_ADMIN']})

    try:
        call('user.renew_2fa_secret', unprivileged_user_fixture.username, {'interval': 60})
        user_obj_id = call('user.query', [['username', '=', unprivileged_user_fixture.username]], {'get': True})['id']
        secret = get_user_secret(user_obj_id)
        yield (unprivileged_user_fixture, secret)
    finally:
        call('privilege.update', privilege[0]['id'], {'roles': []})


@pytest.fixture(scope='module')
def two_factor_full_admin_as_builtin_admin(two_factor_enabled, unprivileged_user_fixture):
    privilege = call('privilege.query', [['local_groups.0.group', '=', unprivileged_user_fixture.group_name]])
    assert len(privilege) > 0, 'Privilege not found'
    builtin_admin = call('group.query', [['name', '=', 'builtin_administrators']], {'get': True})
    user_obj_id = call('user.query', [['username', '=', unprivileged_user_fixture.username]], {'get': True})['id']
    call('group.update', builtin_admin['id'], {'users': builtin_admin['users'] + [user_obj_id]})

    try:
        call('user.renew_2fa_secret', unprivileged_user_fixture.username, {'interval': 60})
        secret = get_user_secret(user_obj_id)
        yield (unprivileged_user_fixture, secret)
    finally:
        call('group.update', builtin_admin['id'], {'users': builtin_admin['users']})


def do_stig_auth(c, user_obj, secret):
    resp = c.call('auth.login_ex', {
        'mechanism': 'PASSWORD_PLAIN',
        'username': user_obj.username,
        'password': user_obj.password
    })
    assert resp['response_type'] == 'OTP_REQUIRED'
    assert resp['username'] == user_obj.username

    resp = c.call('auth.login_ex', {
        'mechanism': 'OTP_TOKEN',
        'otp_token': get_2fa_totp_token(secret)
    })

    assert resp['response_type'] == 'SUCCESS'


@pytest.fixture(scope='module')
def setup_stig(two_factor_full_admin_as_builtin_admin):
    """ Configure STIG and yield admin user object and an authenticated session """
    user_obj, secret = two_factor_full_admin_as_builtin_admin

    # Create websocket connection from prior to STIG being enabled to pass to
    # test methods. This connection will have unrestricted privileges (due to
    # privilege_compose happening before STIG).
    #
    # Tests validating what can be performed under STIG restrictions should create
    # a new websocket session
    with product_type('ENTERPRISE'):
        with set_fips_available(True):
            with client(auth=None) as c:
                # Do two-factor authentication before enabling STIG support
                do_stig_auth(c, user_obj, secret)

                # Disable password authentication for immutable admin accounts
                admin_id = get_excluded_admins()
                for id in admin_id:
                    c.call('user.update', id, {"password_disabled": True})

                c.call('system.security.update', {'enable_fips': True, 'enable_gpos_stig': True}, job=True)
                aal = c.call('auth.get_authenticator_assurance_level')
                assert aal == 'LEVEL_2'

                try:
                    yield {
                        'connection': c,
                        'user_obj': user_obj,
                        'secret': secret
                    }
                finally:
                    c.call('system.security.update', {'enable_fips': False, 'enable_gpos_stig': False}, job=True)
                    for admin in admin_id:
                        c.call('user.update', id, {"password_disabled": False})


# The order of the following tests is significant. We gradually add fixtures that have module scope
# as we finish checking for correct ValidationErrors

def test_nonenterprise_fail(community_product):
    with pytest.raises(ValidationErrors, match='Please contact iX sales for more information.'):
        call('system.security.update', {'enable_gpos_stig': True}, job=True)


def test_nofips_fail(enterprise_product):
    with pytest.raises(ValidationErrors, match='FIPS mode is required in General Purpose OS STIG compatibility mode.'):
        call('system.security.update', {'enable_fips': False, 'enable_gpos_stig': True}, job=True)


def test_no_twofactor_fail(enterprise_product):
    with pytest.raises(ValidationErrors, match='Two factor authentication must be globally enabled.'):
        call('system.security.update', {'enable_fips': True, 'enable_gpos_stig': True}, job=True)


def test_no_twofactor_users_fail(enterprise_product, two_factor_enabled):
    with pytest.raises(ValidationErrors, match='Two factor authentication tokens must be configured for users'):
        call('system.security.update', {'enable_fips': True, 'enable_gpos_stig': True}, job=True)


def test_no_full_admin_users_fail(enterprise_product, two_factor_non_admin):
    with pytest.raises(ValidationErrors, match='At least one local user with full admin privileges must be'):
        call('system.security.update', {'enable_fips': True, 'enable_gpos_stig': True}, job=True)


def test_no_current_cred_no_2fa(enterprise_product, two_factor_full_admin):
    with pytest.raises(ValidationErrors, match='Credential used to enable General Purpose OS STIG compatibility'):
        # root / truenas_admin does not have 2FA and so this should fail
        call('system.security.update', {'enable_fips': True, 'enable_gpos_stig': True}, job=True)


def test_auth_enabled_admin_users_fail(enterprise_product, two_factor_full_admin_as_builtin_admin):
    """ Attempt to enable STIG with password enabled admins still available """
    user_obj, secret = two_factor_full_admin_as_builtin_admin
    with client(auth=None) as c:
        # Do two-factor authentication before using the client for the call
        do_stig_auth(c, user_obj, secret)
        with pytest.raises(ValidationErrors, match='General purpose administrative accounts with password authentication are'):
            # There are immutable admins with passwords enabled, so this should fail
            c.call('system.security.update', {'enable_fips': True, 'enable_gpos_stig': True}, job=True)


# At this point STIG should be enabled on TrueNAS until end of file


def test_stig_enabled_authenticator_assurance_level(setup_stig, clear_ratelimit):
    # Validate that admin user can authenticate and perform operations
    setup_stig['connection'].call('system.info')

    # Auth for account without 2fa should fail
    with client(auth=None) as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': 'root',
            'password': password()
        })

        assert resp['response_type'] == 'AUTH_ERR'

    # We should also be able to create a new websocket connection
    # The previous one was created before enabling STIG
    with client(auth=None) as c:
        do_stig_auth(c, setup_stig['user_obj'], setup_stig['secret'])
        c.call('system.info')


def test_stig_roles_decrease(setup_stig, clear_ratelimit):

    # We need new websocket connection to verify that privileges
    # are appropriately decreased
    with client(auth=None) as c:
        do_stig_auth(c, setup_stig['user_obj'], setup_stig['secret'])

        me = c.call('auth.me')
        for role in c.call('privilege.roles'):
            if role['stig'] is not None:
                assert role['name'] in me['privilege']['roles']
            else:
                assert role['name'] not in me['privilege']['roles']

        assert me['privilege']['web_shell'] is False
        assert me['privilege']['webui_access'] is True


def test_stig_prevent_disable_2fa(setup_stig, clear_ratelimit):
    with client(auth=None) as c:
        do_stig_auth(c, setup_stig['user_obj'], setup_stig['secret'])
        with pytest.raises(Verr, match='Two factor authentication may not be disabled'):
            c.call('auth.twofactor.update', {'enabled': False})

        with pytest.raises(Verr, match='for ssh service is required'):
            c.call('auth.twofactor.update', {'services': {'ssh': False}})


def test_stig_smb_auth_disabled(setup_stig, clear_ratelimit):
    # We need new websocket connection to verify that privileges
    # are appropriately decreased

    smb_user_cnt = setup_stig['connection'].call('user.query', [['smb', '=', True]], {'count': True})
    assert smb_user_cnt == 0

    # We shouldn't be able to create new SMB users
    with pytest.raises(Verr, match='General Purpose OS STIG'):
        setup_stig['connection'].call('user.create', {
            'username': 'CANARY',
            'full_name': 'CANARY',
            'password': 'CANARY',
            'group_create': True,
            'smb': True
        })
