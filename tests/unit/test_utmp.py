import ctypes
import ipaddress
import os
import pam
import pytest
import socket
import uuid

from contextlib import contextmanager
from datetime import datetime, UTC
from middlewared.utils.account import utmp, authenticator, faillock
from middlewared.utils.auth import AUID_UNSET, OTPW_MANAGER
from middlewared.utils.origin import ConnectionOrigin
from time import sleep
from truenas_api_client import Client

UTMP_SESSION_ID = str(uuid.uuid4())
DEFAULT_UTMP_ENTRY = {
    'ut_type': utmp.PyUtmpType.USER_PROCESS,
    'ut_pid': os.getpid(),
    'ut_id': '',
    'ut_user': 'root',
    'ut_line': f'{authenticator.MiddlewareTTYName.WEBSOCKET.value}/1000',
    'ut_host': f'{authenticator.MIDDLEWARE_HOST_PREFIX}.{UTMP_SESSION_ID}',
    'ut_exit': None,
    'ut_tv': datetime.now(UTC),
    'ut_session': os.getsid(os.getpid()),
    'ut_addr': ipaddress.ip_address('169.254.20.20'),
}


v4_origin = ConnectionOrigin(family=socket.AF_INET, rem_addr=ipaddress.ip_address('169.254.20.30'))
v6_origin = ConnectionOrigin(family=socket.AF_INET6, rem_addr=ipaddress.ip_address('fe80::1ff:fe23:4567:890a'))
ssl_origin = ConnectionOrigin(family=socket.AF_INET, rem_addr=ipaddress.ip_address('169.254.20.30'), ssl=True)
unix_origin_noninteractive = ConnectionOrigin(family=socket.AF_UNIX, pid=8675, loginuid=AUID_UNSET)
unix_origin_interactive = ConnectionOrigin(family=socket.AF_UNIX, pid=8675, loginuid=3000)
assert unix_origin_noninteractive.session_is_interactive is False


@pytest.fixture(scope='function')
def fake_session_id():
    return str(uuid.uuid4())


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


@contextmanager
def unix_pam_authenticator(username: str, origin: ConnectionOrigin, session: str):
    pam_hdl = authenticator.UnixPamAuthenticator()

    # First authenticate
    pam_resp = pam_hdl.authenticate(username, origin)
    assert pam_resp.code == pam.PAM_SUCCESS, pam_resp.reason

    # Now login
    pam_resp = pam_hdl.login(session)
    assert pam_resp.code == pam.PAM_SUCCESS, pam_resp.reason

    try:
        yield pam_hdl
    finally:
        pam_resp = pam_hdl.logout()

    assert pam_resp.code == pam.PAM_SUCCESS, pam_resp.reason


@contextmanager
def user_pam_authenticator(username: str, password: str, origin: ConnectionOrigin, session: str):
    pam_hdl = authenticator.UserPamAuthenticator()

    # First authenticate
    pam_resp = pam_hdl.authenticate(username, password, origin)
    assert pam_resp.code == pam.PAM_SUCCESS, pam_resp.reason

    # Now login
    pam_resp = pam_hdl.login(session)
    assert pam_resp.code == pam.PAM_SUCCESS, pam_resp.reason

    try:
        yield pam_hdl
    finally:
        pam_resp = pam_hdl.logout()

    assert pam_resp.code == pam.PAM_SUCCESS, pam_resp.reason


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


def test__utmp_conversion():
    """ Test conversion to / from ctype struct """
    py_entry = utmp.PyUtmpEntry(**DEFAULT_UTMP_ENTRY)
    ctype_entry = py_entry.to_ctype()
    converted = utmp.__parse_utmp_entry(ctypes.pointer(ctype_entry))
    assert py_entry == converted


def test__login_logout():
    py_entry = utmp.PyUtmpEntry(**DEFAULT_UTMP_ENTRY)
    utmp.login(py_entry)
    result = utmp.utmp_query([['ut_line', '=', py_entry.ut_line]], {'get': True})
    result.pop('ut_type_str')
    result.pop('loginuid')
    result.pop('passwd')
    result['ut_addr'] = ipaddress.ip_address(result['ut_addr'])
    new = utmp.PyUtmpEntry(**result)
    assert py_entry == new

    utmp.logout(py_entry)
    result = utmp.utmp_query([['ut_line', '=', py_entry.ut_line]], {'get': True})
    assert result['ut_type_str'] == 'DEAD_PROCESS'


def test__interactive_unix_login(fake_session_id):
    """ interactive unix sessions should generate a utmp entry and be properly identified """
    with unix_pam_authenticator('root', unix_origin_interactive, fake_session_id) as hdl:
        ut_line = hdl.truenas_state.utmp_entry.ut_line
        entry = utmp.utmp_query([['ut_line', '=', ut_line]], {'get': True})
        assert entry['ut_user'] == 'root'
        assert entry['ut_pid'] == os.getpid()
        assert entry['ut_type_str'] == 'USER_PROCESS'
        assert entry['ut_host'].endswith('PID8675')
        assert fake_session_id in entry['ut_host']
        assert hdl.truenas_state.utmp_session_id is not None
        assert hdl.truenas_state.utmp_session_id not in authenticator.AVAILABLE_SESSION_IDS
        session_id = hdl.truenas_state.utmp_session_id

    entry = utmp.utmp_query([['ut_line', '=', ut_line]], {'get': True})
    assert entry['ut_type_str'] == 'DEAD_PROCESS'
    assert session_id in authenticator.AVAILABLE_SESSION_IDS


def test__noninteractive_unix_login(fake_session_id):
    """ Non-interactive sessions shouldn't generate a utmp entry. """
    with unix_pam_authenticator('root', unix_origin_noninteractive, fake_session_id) as hdl:
        assert hdl.truenas_state.utmp_session_id is None
        assert hdl.truenas_state.utmp_entry is None


def test__ipv4_login(fake_session_id, admin_user):
    with user_pam_authenticator(admin_user['username'], admin_user['password'], v4_origin, fake_session_id) as hdl:
        ut_line = hdl.truenas_state.utmp_entry.ut_line
        entry = utmp.utmp_query([['ut_line', '=', ut_line]], {'get': True})
        assert entry['ut_user'] == admin_user['username']
        assert entry['ut_pid'] == os.getpid()
        assert entry['ut_type_str'] == 'USER_PROCESS'
        assert entry['ut_host'].endswith(f'IP{v4_origin.rem_addr}')
        assert entry['ut_addr'] == str(v4_origin.rem_addr)
        assert fake_session_id in entry['ut_host']
        assert hdl.truenas_state.utmp_session_id is not None
        assert hdl.truenas_state.utmp_session_id not in authenticator.AVAILABLE_SESSION_IDS
        session_id = hdl.truenas_state.utmp_session_id

    entry = utmp.utmp_query([['ut_line', '=', ut_line]], {'get': True})
    assert entry['ut_type_str'] == 'DEAD_PROCESS'
    assert session_id in authenticator.AVAILABLE_SESSION_IDS


def test__ipv6_login(fake_session_id, admin_user):
    with user_pam_authenticator(admin_user['username'], admin_user['password'], v6_origin, fake_session_id) as hdl:
        ut_line = hdl.truenas_state.utmp_entry.ut_line
        entry = utmp.utmp_query([['ut_line', '=', ut_line]], {'get': True})
        assert entry['ut_line'].startswith('ws/')
        assert entry['ut_user'] == admin_user['username']
        assert entry['ut_pid'] == os.getpid()
        assert entry['ut_type_str'] == 'USER_PROCESS'
        assert entry['ut_host'].endswith(f'IP{v6_origin.rem_addr}')
        assert entry['ut_addr'] == str(v6_origin.rem_addr)
        assert fake_session_id in entry['ut_host']
        assert hdl.truenas_state.utmp_session_id is not None
        assert hdl.truenas_state.utmp_session_id not in authenticator.AVAILABLE_SESSION_IDS
        session_id = hdl.truenas_state.utmp_session_id

    entry = utmp.utmp_query([['ut_line', '=', ut_line]], {'get': True})
    assert entry['ut_type_str'] == 'DEAD_PROCESS'
    assert session_id in authenticator.AVAILABLE_SESSION_IDS


def test__wss_login(fake_session_id, admin_user):
    with user_pam_authenticator(admin_user['username'], admin_user['password'], ssl_origin, fake_session_id) as hdl:
        ut_line = hdl.truenas_state.utmp_entry.ut_line
        entry = utmp.utmp_query([['ut_line', '=', ut_line]], {'get': True})
        assert entry['ut_line'].startswith('wss/')
        assert entry['ut_user'] == admin_user['username']
        assert entry['ut_pid'] == os.getpid()
        assert entry['ut_type_str'] == 'USER_PROCESS'
        assert entry['ut_host'].endswith(f'IP{ssl_origin.rem_addr}')
        assert entry['ut_addr'] == str(ssl_origin.rem_addr)
        assert fake_session_id in entry['ut_host']
        assert hdl.truenas_state.utmp_session_id is not None
        assert hdl.truenas_state.utmp_session_id not in authenticator.AVAILABLE_SESSION_IDS
        session_id = hdl.truenas_state.utmp_session_id

    entry = utmp.utmp_query([['ut_line', '=', ut_line]], {'get': True})
    assert entry['ut_type_str'] == 'DEAD_PROCESS'
    assert session_id in authenticator.AVAILABLE_SESSION_IDS


def test__session_limits(fake_session_id, admin_user, pam_stig):
    # max logins is 10
    args = [admin_user['username'], admin_user['password'], v4_origin, fake_session_id]
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
        with pytest.raises(Exception, match='Permission denied'):
            with user_pam_authenticator(*args):
                pass


def test__session_login_fail_unlock_middleware(fake_session_id, admin_user, pam_stig):
    # Sanity check that our pasword works
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], admin_user['password'], v6_origin)
    assert resp.code == pam.PAM_SUCCESS

    # First should be an AUTH_ERR
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], 'canary', v6_origin)
    assert resp.code == pam.PAM_AUTH_ERR

    # So should be second
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], 'canary', v6_origin)
    assert resp.code == pam.PAM_AUTH_ERR

    # This time the PAM code changes to PAM_PERM_DENIED to indicate that account is locked
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], 'canary', v6_origin)
    assert resp.code == pam.PAM_PERM_DENIED
    assert resp.reason == 'Account is locked due to failed login attempts.'

    # Account is now tally locked
    assert faillock.is_tally_locked(admin_user['username'])

    # Auth attempt with correct password should fail
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], admin_user['password'], v6_origin)
    assert resp.code == pam.PAM_PERM_DENIED

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
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], admin_user['password'], v6_origin)
    assert resp.code == pam.PAM_SUCCESS


def test__session_login_fail_unlock_time(fake_session_id, admin_user, pam_stig):
    # Sanity check that our pasword works
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], admin_user['password'], v4_origin)
    assert resp.code == pam.PAM_SUCCESS

    # First should be an AUTH_ERR
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], 'canary', v4_origin)
    assert resp.code == pam.PAM_AUTH_ERR

    # So should be second
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], 'canary', v4_origin)
    assert resp.code == pam.PAM_AUTH_ERR

    # This time the PAM code changes to PAM_PERM_DENIED to indicate that account is locked
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], 'canary', v4_origin)
    assert resp.code == pam.PAM_PERM_DENIED
    assert resp.reason == 'Account is locked due to failed login attempts.'

    # Account is now tally locked
    assert faillock.is_tally_locked(admin_user['username'])

    # Auth attempt with correct password should fail
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], admin_user['password'], v4_origin)
    assert resp.code == pam.PAM_PERM_DENIED

    # rewrite pam middleware file so that we don't have to wait 15 minutes
    for path in ('/etc/pam.d/middleware', '/etc/pam.d/common-auth-unix'):
        fd = os.open(path, os.O_RDWR)
        try:
            data = os.pread(fd, os.fstat(fd).st_size, 0)
            data = data.replace(f'unlock_time={faillock.UNLOCK_TIME}'.encode(), b'unlock_time=5')
        finally:
            os.close(fd)

        with open(path, 'wb') as f:
            f.write(data)
            f.flush()

    sleep(5)
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], admin_user['password'], v4_origin)
    assert resp.code == pam.PAM_SUCCESS


def test__otpw_login_admin_otp(fake_session_id, admin_user):
    # When an admin user generates an OTPW for an account we set a special account flag
    password = OTPW_MANAGER.generate_for_uid(admin_user['uid'], True)
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], password, v4_origin)
    assert resp.code == pam.PAM_SUCCESS
    assert authenticator.AccountFlag.OTPW in resp.user_info['account_attributes']
    assert authenticator.AccountFlag.PASSWORD_CHANGE_REQUIRED in resp.user_info['account_attributes']


def test__otpw_login_nonadmin_otp(fake_session_id, admin_user):
    password = OTPW_MANAGER.generate_for_uid(admin_user['uid'])
    pam_hdl = authenticator.UserPamAuthenticator()
    resp = pam_hdl.authenticate(admin_user['username'], password, v4_origin)
    assert resp.code == pam.PAM_SUCCESS
    assert authenticator.AccountFlag.OTPW in resp.user_info['account_attributes']
    assert authenticator.AccountFlag.PASSWORD_CHANGE_REQUIRED not in resp.user_info['account_attributes']


def test__pam_oath(admin_user, pam_stig):
    # Set a twofactor secret. We don't actually need to know it since we're checking for change in
    # PAM conversation
    with Client() as c2:
        c2.call('user.renew_2fa_secret', admin_user['username'], {})

    p = pam.pam()
    ok = p.authenticate(admin_user['username'], admin_user['password'], service='sshd')
    # python pam can't handle a proper PAM conversation and so fails, but it's sufficient
    # to validate we're getting prompted for OTP to cover NAS-136065
    assert not ok
    assert len(p.messages) == 2

    assert 'One-time password (OATH)' in p.messages[1]
