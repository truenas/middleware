import ctypes
import ipaddress
import os
import pam
import pytest
import socket
import uuid

from contextlib import contextmanager
from datetime import datetime, UTC
from middlewared.utils.account import utmp, authenticator
from middlewared.utils.auth import AUID_UNSET
from middlewared.utils.origin import ConnectionOrigin

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


@contextmanager
def unix_pam_authenticator(username: str, origin: ConnectionOrigin, session: str):
    pam_hdl = authenticator.TrueNAS_UnixPamAuthenticator()

    # First authenticate
    pam_resp = pam_hdl.authenticate(username)
    assert pam_resp.code == pam.PAM_SUCCESS, pam_resp.reason

    # Now login
    pam_resp = pam_hdl.login(session, origin)
    assert pam_resp.code == pam.PAM_SUCCESS, pam_resp.reason

    try:
        yield pam_hdl
    finally:
        pam_resp = pam_hdl.logout()

    assert pam_resp.code == pam.PAM_SUCCESS, pam_resp.reason


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
        ut_line = hdl.truenas_utmp_entry.ut_line
        entry = utmp.utmp_query([['ut_line', '=', ut_line]], {'get': True})
        assert entry['ut_user'] == 'root'
        assert entry['ut_pid'] == os.getpid()
        assert entry['ut_type_str'] == 'USER_PROCESS'
        assert entry['ut_host'].endswith('PID8675')
        assert fake_session_id in entry['ut_host']
        assert hdl.truenas_utmp_session_id is not None
        assert hdl.truenas_utmp_session_id not in authenticator.AVAILABLE_SESSION_IDS

    entry = utmp.utmp_query([['ut_line', '=', ut_line]], {'get': True})
    assert entry['ut_type_str'] == 'DEAD_PROCESS'
    assert hdl.truenas_utmp_session_id in authenticator.AVAILABLE_SESSION_IDS


def test__noninteractive_unix_login(fake_session_id):
    """ Non-interactive sessions shouldn't generate a utmp entry. """
    with unix_pam_authenticator('root', unix_origin_noninteractive, fake_session_id) as hdl:
        assert hdl.truenas_utmp_session_id is None
        assert hdl.truenas_utmp_entry is None
