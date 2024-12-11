import errno
import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.product import enable_stig, product_type, set_fips_available
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


@pytest.fixture(scope='function')
def two_factor_enabled():
    with enabled_twofactor_auth() as two_factor_config:
        yield two_factor_config


@pytest.fixture(scope='function')
def setup_stig():
    # We need authenticated client to undo assurance level
    with client() as c:
        with enable_stig():
            # Force reconfiguration for STIG
            call('system.security.configure_stig', {'enable_gpos_stig': True})
            aal = call('auth.get_authenticator_assurance_level')
            assert aal == 'LEVEL_2'

            try:
                yield
            finally:
                # Drop assurance level so that we can remove mock
                # reliably
                c.call('auth.set_authenticator_assurance_level', 'LEVEL_1')


@pytest.fixture(scope='function')
def two_factor_non_admin(two_factor_enabled, unprivileged_user_fixture):
    privilege = call('privilege.query', [['local_groups.0.group', '=', unprivileged_user_fixture.group_name]])
    assert len(privilege) > 0, 'Privilege not found'
    call('privilege.update', privilege[0]['id'], {'roles': ['SHARING_ADMIN']})

    try:
        call('user.renew_2fa_secret', unprivileged_user_fixture.username, {'interval': 60})
        yield unprivileged_user_fixture
    finally:
        call('privilege.update', privilege[0]['id'], {'roles': []})


@pytest.fixture(scope='function')
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


def test_nonenterprise_fail(community_product):
    with pytest.raises(ValidationErrors, match='Please contact iX sales for more information.'):
        call('system.security.update', {'enable_gpos_stig': True}, job=True)


def test_nofips_fail(enterprise_product):
    with pytest.raises(ValidationErrors, match='FIPS mode is required in STIG compatibility mode.'):
        call('system.security.update', {'enable_fips': False, 'enable_gpos_stig': True}, job=True)


def test_no_twofactor_fail(enterprise_product):
    with pytest.raises(ValidationErrors, match='Two factor authentication must be globally enabled.'):
        call('system.security.update', {'enable_fips': True, 'enable_gpos_stig': True}, job=True)


def test_no_twofactor_users_fail(enterprise_product, two_factor_enabled):
    with pytest.raises(ValidationErrors, match='Two factor authentication tokens must be configured for users'):
        call('system.security.update', {'enable_fips': True, 'enable_gpos_stig': True}, job=True)


def test_no_full_admin_users_fail(enterprise_product, two_factor_non_admin):
    with pytest.raises(ValidationErrors, match='At least one local user with full admin privileges and must be'):
        call('system.security.update', {'enable_fips': True, 'enable_gpos_stig': True}, job=True)


def test_no_current_cred_no_2fa(enterprise_product, two_factor_full_admin):
    with pytest.raises(ValidationErrors, match='Credential used to enable General Purpose OS STIG compatibility'):
        # root / truenas_admin does not have 2FA and so this should fail
        call('system.security.update', {'enable_fips': True, 'enable_gpos_stig': True}, job=True)


def test_stig_enabled_authenticator_assurance_level(setup_stig, two_factor_full_admin):
    # Validate that admin user can authenticate and perform operations
    user_obj, secret = two_factor_full_admin
    with client(auth=None) as c:
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

    # Auth for account without 2fa should fail
    with pytest.raises(CallError) as ce:
        with client():
            pass

    assert ce.value.errno == errno.EOPNOTSUPP
