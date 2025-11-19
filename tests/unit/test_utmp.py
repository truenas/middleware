import ipaddress
import os
import pyotp
import pytest
import socket
import truenas_pam_session

from contextlib import contextmanager
from middlewared.utils.account import authenticator, faillock
from middlewared.utils.auth import AUID_UNSET, OTPW_MANAGER
from middlewared.utils.origin import ConnectionOrigin
from time import sleep
from truenas_api_client import Client
from truenas_pypam import PAMCode
import truenas_pam_session


v4_origin = ConnectionOrigin(
    family=socket.AF_INET,
    rem_addr=ipaddress.ip_address('169.254.20.30'),
    rem_port=8675,
    loc_addr=ipaddress.ip_address('169.254.20.40'),
    loc_port=8676
)
v6_origin = ConnectionOrigin(
    family=socket.AF_INET6,
    rem_addr=ipaddress.ip_address('fe80::1ff:fe23:4567:890a'),
    rem_port=8675,
    loc_addr=ipaddress.ip_address('fe80::1ff:fe23:4567:890b'),
    loc_port=8676
)
ssl_origin = ConnectionOrigin(
    family=socket.AF_INET,
    rem_addr=ipaddress.ip_address('169.254.20.30'),
    rem_port=8675,
    loc_addr=ipaddress.ip_address('169.254.20.40'),
    loc_port=8676,
    ssl=True
)
unix_origin_noninteractive = ConnectionOrigin(family=socket.AF_UNIX, uid=0, pid=8675, loginuid=AUID_UNSET)
unix_origin_interactive = ConnectionOrigin(family=socket.AF_UNIX, uid=3000, pid=8675, loginuid=3000)
assert unix_origin_noninteractive.session_is_interactive is False


@pytest.fixture(scope='function')
def pam_stig():
    with Client() as c:
        c.call('datastore.update', 'system.security', 1, {'enable_gpos_stig': True})
        c.call('etc.generate', 'pam')
        c.call('etc.generate', 'pam_middleware')
        c.call('auth.twofactor.update', {'enabled': True, 'services': {'ssh': True}})
        c.call('etc.generate', 'ssh')
        try:
            yield c
        finally:
            c.call('datastore.update', 'system.security', 1, {'enable_gpos_stig': False})
            c.call('etc.generate', 'pam')
            c.call('etc.generate', 'pam_middleware')
            c.call('auth.twofactor.update', {'enabled': False, 'services': {'ssh': False}})
            c.call('etc.generate', 'ssh')


@pytest.fixture(scope='function')
def enable_2fa():
    with Client() as c:
        twofactor_config = c.call('auth.twofactor.update', {'enabled': True})
        try:
            yield twofactor_config
        finally:
            c.call('auth.twofactor.update', {'enabled': False})


@contextmanager
def unix_pam_authenticator(username: str, origin: ConnectionOrigin):
    # Constructor now takes username and origin
    pam_hdl = authenticator.UnixPamAuthenticator(username=username, origin=origin)

    # Authenticate (no origin parameter)
    pam_resp = pam_hdl.authenticate(username)
    assert pam_resp.code == PAMCode.PAM_SUCCESS, pam_resp.reason

    # Login (no session parameter)
    pam_resp = pam_hdl.login()
    assert pam_resp.code == PAMCode.PAM_SUCCESS, pam_resp.reason

    try:
        yield pam_hdl
    finally:
        pam_resp = pam_hdl.logout()

    assert pam_resp.code == PAMCode.PAM_SUCCESS, pam_resp.reason


@contextmanager
def user_pam_authenticator(username: str, password: str, origin: ConnectionOrigin):
    # Constructor now takes username and origin
    pam_hdl = authenticator.UserPamAuthenticator(username=username, origin=origin)

    # Authenticate (no origin parameter)
    pam_resp = pam_hdl.authenticate(username, password)
    assert pam_resp.code == PAMCode.PAM_SUCCESS, pam_resp.reason

    # Login (no session parameter)
    pam_resp = pam_hdl.login()
    assert pam_resp.code == PAMCode.PAM_SUCCESS, pam_resp.reason

    try:
        yield pam_hdl
    finally:
        pam_resp = pam_hdl.logout()

    assert pam_resp.code == PAMCode.PAM_SUCCESS, pam_resp.reason


@contextmanager
def create_user(name, **kwargs):
    with Client() as c:
        usr = c.call('user.create', {
            'username': name,
            'full_name': name,
            'random_password': True,
            'group_create': True
        } | kwargs)
        try:
            yield usr

        finally:
            c.call('user.delete', usr['id'])


@pytest.fixture(scope='module')
def admin_user():
    with create_user('admin_user') as u:
        with Client() as c:
            ba_id = c.call('group.query', [['gid', '=', 544]], {'get': True})['id']
            c.call('user.update', u['id'], {'groups': u['groups'] + [ba_id]})
            yield u


@pytest.fixture(scope='function')
def oath_admin_user(admin_user):
    with Client() as c:
        c.call('user.renew_2fa_secret', admin_user['username'], {})
        user_2fa_config = c.call(
            'datastore.query', 'account.twofactor_user_auth',
            [['user_id', '=', admin_user['id']]], {'get': True}
        )
        try:
            yield admin_user | {
                'twofactor_secret': user_2fa_config['secret'],
                'interval': user_2fa_config['interval'],
                'digits': user_2fa_config['otp_digits']
            }
        finally:
            c.call('user.unset_2fa_secret', admin_user['username'])


def get_totp_token(secret, interval, digits):
    return pyotp.TOTP(secret, interval=interval, digits=digits).now()


# test__utmp_conversion and test__login_logout removed - utmp functionality
# is now managed internally by pam_truenas module


def test__interactive_unix_login():
    """ interactive unix sessions should generate a session keyring entry """
    with unix_pam_authenticator('root', unix_origin_interactive) as hdl:
        # Verify session UUID was set
        assert hdl.session_uuid is not None

        # Query session from keyring
        session = truenas_pam_session.get_session_by_id(str(hdl.session_uuid))
        assert session is not None
        assert session.username == 'root'
        assert session.service == 'middleware-unix'
        assert session.origin_family == 'AF_UNIX'
        assert session.origin.pid == unix_origin_interactive.pid
        assert session.origin.uid == unix_origin_interactive.uid
        assert session.origin.loginuid == unix_origin_interactive.uid

        session_uuid = hdl.session_uuid

    # Verify session is removed after logout
    session = truenas_pam_session.get_session_by_id(str(session_uuid))
    assert session is None


def test__noninteractive_unix_login():
    """ Non-interactive sessions should still generate a session keyring entry. """
    with unix_pam_authenticator('root', unix_origin_noninteractive) as hdl:
        # Verify session UUID was set
        assert hdl.session_uuid is not None

        # Query session from keyring
        session = truenas_pam_session.get_session_by_id(str(hdl.session_uuid))
        assert session is not None
        assert session.username == 'root'
        assert session.origin_family == 'AF_UNIX'
        assert session.origin.pid == 8675
        assert session.origin.loginuid == AUID_UNSET  # non-interactive


def test__ipv4_login(admin_user):
    with user_pam_authenticator(admin_user['username'], admin_user['password'], v4_origin) as hdl:
        # Verify session UUID was set
        assert hdl.session_uuid is not None

        # Query session from keyring
        session = truenas_pam_session.get_session_by_id(str(hdl.session_uuid))
        assert session is not None
        assert session.username == admin_user['username']
        assert session.service == 'middleware'
        assert session.origin_family == 'AF_INET'
        assert str(session.origin.remote_addr) == str(v4_origin.rem_addr)
        assert session.origin.ssl is False

        session_uuid = hdl.session_uuid

    # Verify session is removed after logout
    session = truenas_pam_session.get_session_by_id(str(session_uuid))
    assert session is None


def test__ipv6_login(admin_user):
    with user_pam_authenticator(admin_user['username'], admin_user['password'], v6_origin) as hdl:
        # Verify session UUID was set
        assert hdl.session_uuid is not None

        # Query session from keyring
        session = truenas_pam_session.get_session_by_id(str(hdl.session_uuid))
        assert session is not None
        assert session.username == admin_user['username']
        assert session.service == 'middleware'
        assert session.origin_family == 'AF_INET6'
        assert str(session.origin.remote_addr) == str(v6_origin.rem_addr)
        assert session.origin.ssl is False

        session_uuid = hdl.session_uuid

    # Verify session is removed after logout
    session = truenas_pam_session.get_session_by_id(str(session_uuid))
    assert session is None


def test__wss_login(admin_user):
    with user_pam_authenticator(admin_user['username'], admin_user['password'], ssl_origin) as hdl:
        # Verify session UUID was set
        assert hdl.session_uuid is not None

        # Query session from keyring
        session = truenas_pam_session.get_session_by_id(str(hdl.session_uuid))
        assert session is not None
        assert session.username == admin_user['username']
        assert session.service == 'middleware'
        assert session.origin_family == 'AF_INET'
        assert str(session.origin.remote_addr) == str(ssl_origin.rem_addr)
        assert session.origin.ssl is True

        session_uuid = hdl.session_uuid

    # Verify session is removed after logout
    session = truenas_pam_session.get_session_by_id(str(session_uuid))
    assert session is None


def test__session_limits(admin_user, pam_stig):
    # max logins is 10
    args = [admin_user['username'], admin_user['password'], v4_origin]
    with (
        user_pam_authenticator(*args),
        user_pam_authenticator(*args),
        user_pam_authenticator(*args),
        user_pam_authenticator(*args),
        user_pam_authenticator(*args),
        user_pam_authenticator(*args),
        user_pam_authenticator(*args),
        user_pam_authenticator(*args),
        user_pam_authenticator(*args),
        user_pam_authenticator(*args),
    ):
        with pytest.raises(Exception, match='PAM_PERM_DENIED'):
            with user_pam_authenticator(*args):
                pass


def test__session_login_fail_unlock_middleware(admin_user, pam_stig):
    # Sanity check that our password works
    pam_hdl = authenticator.UserPamAuthenticator(username=admin_user['username'], origin=v6_origin)
    resp = pam_hdl.authenticate(admin_user['username'], admin_user['password'])
    assert resp.code == PAMCode.PAM_SUCCESS

    # First should be an AUTH_ERR
    pam_hdl = authenticator.UserPamAuthenticator(username=admin_user['username'], origin=v6_origin)
    resp = pam_hdl.authenticate(admin_user['username'], 'canary')
    assert resp.code == PAMCode.PAM_AUTH_ERR

    # So should be second
    pam_hdl = authenticator.UserPamAuthenticator(username=admin_user['username'], origin=v6_origin)
    resp = pam_hdl.authenticate(admin_user['username'], 'canary')
    assert resp.code == PAMCode.PAM_AUTH_ERR

    # So should third
    pam_hdl = authenticator.UserPamAuthenticator(username=admin_user['username'], origin=v6_origin)
    resp = pam_hdl.authenticate(admin_user['username'], 'canary')
    assert resp.code == PAMCode.PAM_AUTH_ERR

    # This time the PAM code changes to PAM_PERM_DENIED to indicate that account is locked
    pam_hdl = authenticator.UserPamAuthenticator(username=admin_user['username'], origin=v6_origin)
    resp = pam_hdl.authenticate(admin_user['username'], 'canary')
    assert resp.code == PAMCode.PAM_PERM_DENIED
    assert resp.reason == 'Account is locked due to failed login attempts.'

    # Account is now tally locked
    assert faillock.is_tally_locked(admin_user['username'])

    # Auth attempt with correct password should fail
    pam_hdl = authenticator.UserPamAuthenticator(username=admin_user['username'], origin=v6_origin)
    resp = pam_hdl.authenticate(admin_user['username'], admin_user['password'])
    assert resp.code == PAMCode.PAM_PERM_DENIED

    with Client() as c:
        entry = c.call('user.query', [['username', '=', admin_user['username']]], {'get': True})
        # Middleware should now see entry as locked.
        assert entry['locked']

        # Locked condition should be removable via middleware
        c.call('user.update', entry['id'], {'locked': False})

        # Entry is no longer locked in PAM
        assert not faillock.is_tally_locked(admin_user['username'])

        entry = c.call('user.query', [['username', '=', admin_user['username']]], {'get': True})
        # Middleware should now see entry as unlocked.
        assert not entry['locked']

    # Auth attempt with correct password should succeed after unlock
    pam_hdl = authenticator.UserPamAuthenticator(username=admin_user['username'], origin=v6_origin)
    resp = pam_hdl.authenticate(admin_user['username'], admin_user['password'])
    assert resp.code == PAMCode.PAM_SUCCESS


def test__otpw_login_admin_otp(admin_user):
    # When an admin user generates an OTPW for an account we set a special account flag
    password = OTPW_MANAGER.generate_for_uid(admin_user['uid'], True)
    pam_hdl = authenticator.UserPamAuthenticator(username=admin_user['username'], origin=v4_origin)
    resp = pam_hdl.authenticate(admin_user['username'], password)
    assert resp.code == PAMCode.PAM_SUCCESS
    assert authenticator.AccountFlag.OTPW in resp.user_info['account_attributes']
    assert authenticator.AccountFlag.PASSWORD_CHANGE_REQUIRED in resp.user_info['account_attributes']


def test__otpw_login_nonadmin_otp(admin_user):
    password = OTPW_MANAGER.generate_for_uid(admin_user['uid'])
    pam_hdl = authenticator.UserPamAuthenticator(username=admin_user['username'], origin=v4_origin)
    resp = pam_hdl.authenticate(admin_user['username'], password)
    assert resp.code == PAMCode.PAM_SUCCESS
    assert authenticator.AccountFlag.OTPW in resp.user_info['account_attributes']
    assert authenticator.AccountFlag.PASSWORD_CHANGE_REQUIRED not in resp.user_info['account_attributes']


def test__pam_oath_no2fa(admin_user, enable_2fa):
    pam_hdl = authenticator.UserPamAuthenticator(username=admin_user['username'], origin=v4_origin)
    resp = pam_hdl.authenticate(admin_user['username'], admin_user['password'])

    # We should have user_unknown=ignore in pam config so accounts missing from users.oath file
    # will retrieve last PAM status (success hopefully).
    assert resp.code == PAMCode.PAM_SUCCESS


def test__pam_oath_2fa(oath_admin_user, enable_2fa):
    pam_hdl = authenticator.UserPamAuthenticator(username=oath_admin_user['username'], origin=v4_origin)
    resp = pam_hdl.authenticate(oath_admin_user['username'], oath_admin_user['password'])

    # Should get PAM_CONV_AGAIN indicating 2FA is required
    assert resp.code == PAMCode.PAM_CONV_AGAIN

    # Verify the message contains OATH prompt
    assert resp.reason is not None
    assert 'One-time password (OATH)' in resp.reason

    otp_token = get_totp_token(
        secret=oath_admin_user['twofactor_secret'],
        interval=oath_admin_user['interval'],
        digits=oath_admin_user['digits']
    )

    resp = pam_hdl.authenticate_oath(otp_token)
    assert resp.code == PAMCode.PAM_SUCCESS
