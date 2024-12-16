import errno
import pytest

from middlewared.service_exception import CallError
from middlewared.service_exception import ValidationErrors as Verr
from middlewared.test.integration.assets.product import product_type, set_fips_available
from middlewared.test.integration.assets.two_factor_auth import (
    enabled_twofactor_auth, get_user_secret, get_2fa_totp_token
)
from middlewared.test.integration.utils import call, client
from truenas_api_client import ValidationErrors


@pytest.fixture(scope='function')
def enterprise_product():
    with product_type('SCALE_ENTERPRISE'):
        with set_fips_available(True):
            yield


@pytest.fixture(scope='function')
def community_product():
    with product_type('SCALE'):
        with set_fips_available(False):
            yield


@pytest.fixture(scope='module')
def two_factor_enabled():
    with enabled_twofactor_auth() as two_factor_config:
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
def setup_stig(two_factor_full_admin):
    """ Configure STIG and yield admin user object and an authenticated session """
    user_obj, secret = two_factor_full_admin

    # Create websocket connection from prior to STIG being enabled to pass to
    # test methods. This connection will have unrestricted privileges (due to
    # privilege_compose happening before STIG).
    #
    # Tests validating what can be performed under STIG restrictions should create
    # a new websocket session
    with product_type('SCALE_ENTERPRISE'):
        with set_fips_available(True):
            with client(auth=None) as c:
                # Do two-factor authentication before enabling STIG support
                do_stig_auth(c, user_obj, secret)
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


# At this point STIG should be enabled on TrueNAS until end of file


def test_stig_enabled_authenticator_assurance_level(setup_stig):
    # Validate that admin user can authenticate and perform operations
    setup_stig['connection'].call('system.info')

    # Auth for account without 2fa should fail
    with pytest.raises(CallError) as ce:
        with client():
            pass

    assert ce.value.errno == errno.EOPNOTSUPP

    # We should also be able to create a new websocket connection
    # The previous one was created before enabling STIG
    with client(auth=None) as c:
        do_stig_auth(c, setup_stig['user_obj'], setup_stig['secret'])
        c.call('system.info')


def test_stig_roles_decrease(setup_stig):

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


def test_stig_smb_auth_disabled(setup_stig):
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
