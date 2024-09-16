import os
import pam
import pwd
import pytest
import tdb

from collections.abc import Generator
from contextlib import contextmanager
from middlewared.utils import crypto
from middlewared.utils import user_api_key
from time import monotonic

EXPIRED_TS = 1
BASE_ID = 1325
LEGACY_ENTRY_KEY = 'rtpz6u16l42XJJGy5KMJOVfkiQH7CyitaoplXy7TqFTmY7zHqaPXuA1ob07B9bcB'
LEGACY_ENTRY_HASH = '$pbkdf2-sha256$29000$CyGktHYOwXgvBYDQOqc05g$nK1MMvVuPGHMvUENyR01qNsaZjgGmlt3k08CRuC4aTI'
INVALID_HASH_TYPE = '$pbkdf2-canary$29000$CyGktHYOwXgvBYDQOqc05g$nK1MMvVuPGHMvUENyR01qNsaZjgGmlt3k08CRuC4aTI'
INVALID_SALT = '$pbkdf2-sha256$29000$CyGktHYOwXgvBYDQOqc0*g$nK1MMvVuPGHMvUENyR01qNsaZjgGmlt3k08CRuC4aTI'
INVALID_HASH = '$pbkdf2-sha256$29000$CyGktHYOwXgvBYDQOqc05g$nK1MMvVuPGHMvUENyR01qNsaZjgGmlt3k08CRuC4a*I'
MISSING_SALT = '$pbkdf2-sha256$29000$$nK1MMvVuPGHMvUENyR01qNsaZjgGmlt3k08CRuC4aTI'
MISSING_HASH = '$pbkdf2-sha256$29000$CyGktHYOwXgvBYDQOqc05g$'
EMPTY_HASH_STRING = ''

PAM_DIR = '/etc/pam.d'
PAM_FILE = 'middleware-api-key'
PAM_AUTH_LINE = 'auth  [success=1 default=die]      pam_tdb.so debug '
PAM_FAIL_DELAY = 1.50  # pam_fail_delay is 2s, but we need a little wiggle-room

PAM_FILE_REMAINING_CONTENTS = """
@include common-auth-unix
@include common-account
password        required        pam_deny.so
session required        pam_deny.so
"""


def write_tdb_file(
    username: str,
    hashlist: list[str],
    expired: bool = False
) -> int:
    """
    Generate a tdb file based on the specified parameters
    The resulting TDB will have one entry for `username` and
    a varying amount of hashes.

    Although each hash supports a separate expiry, we are only
    concerned in these tests expired hashes generate PAM_AUTH_ERR
    as expected.
    """

    keys = []
    idx = 0

    for idx, thehash in enumerate(hashlist):
        keys.append(user_api_key.UserApiKey(
            userhash=thehash,
            dbid=BASE_ID + idx,
            expiry=EXPIRED_TS if expired else 0
        ))

    entry = user_api_key.PamTdbEntry(username=username, keys=keys)

    user_api_key.flush_user_api_keys([entry])

    return BASE_ID + idx


def truncate_tdb_file(username: str) -> None:
    """
    Truncate tdb entry to make pascal string point off end of buffer
    If this sets PAM_AUTH_ERR then we need to look closely to make
    sure we don't have parser issues in pam_tdb.c
    """
    hdl = tdb.open(user_api_key.PAM_TDB_FILE)
    try:
        data = hdl.get(username.encode())
        hdl.store(username.encode(), data[0:len(data) - 5])
    finally:
        hdl.close()


def make_tdb_garbage(username: str) -> None:
    """ fill entry with non-api-key data """
    hdl = tdb.open(user_api_key.PAM_TDB_FILE)
    try:
        hdl.get(username.encode())
        hdl.store(username.encode(), b'meow')
    finally:
        hdl.close()


def make_null_tdb_entry(username: str) -> None:
    """ throw some nulls into the mix for fun """
    hdl = tdb.open(user_api_key.PAM_TDB_FILE)
    try:
        hdl.get(username.encode())
        hdl.store(username.encode(), b'\x00' * 128)
    finally:
        hdl.close()


@contextmanager
def pam_service(
    file_name: str = PAM_FILE,
    admin_user: str | None = None,
) -> Generator[str, None, None]:
    """ Create a pam service file for pam_tdb.so """
    auth_entry = PAM_AUTH_LINE
    if admin_user:
        auth_entry += f'truenas_admin={admin_user}'

    pam_service_path = os.path.join(PAM_DIR, file_name)

    with open(pam_service_path, 'w') as f:
        f.write(auth_entry)
        f.write(PAM_FILE_REMAINING_CONTENTS)
        f.flush()

    try:
        yield file_name
    finally:
        os.remove(pam_service_path)


@contextmanager
def fail_delay() -> Generator[None, None, None]:
    """
    Assert if failure case finishes faster than our expected fail delay, which
    is an amount of time randomly distributed (by up to 25%) about the longest
    value set. In our case, this is 2 seconds and so the can be anywhere
    between 1.5 seconds and 2.5 seconds. We are only concerned in these tests
    about the lower margin to ensure that we aren't immediately failing. If
    we don't insert a failure delay then this may introduce vulnerability to
    timing attacks on passwords.
    """
    now = monotonic()
    yield
    elapsed = monotonic() - now
    assert elapsed > PAM_FAIL_DELAY


@pytest.fixture(scope='module')
def current_username():
    """ for simplicity sake we'll test against current user """
    return pwd.getpwuid(os.geteuid()).pw_name


def test_unknown_user(current_username):
    """
    A user without an entry in the file should fail with appropriate error
    and generate a fail delay
    """
    db_id = write_tdb_file(current_username, [LEGACY_ENTRY_HASH])
    with pam_service(admin_user=current_username) as svc:
        p = pam.pam()
        with fail_delay():
            authd = p.authenticate('canary', f'{db_id}-{LEGACY_ENTRY_KEY}', service=svc)
            assert authd is False
            assert p.code == pam.PAM_USER_UNKNOWN


def test_legacy_auth_admin(current_username):
    """ This should succeed for specified admin user """
    db_id = write_tdb_file(current_username, [LEGACY_ENTRY_HASH])
    with pam_service(admin_user=current_username) as svc:
        p = pam.pam()
        authd = p.authenticate(current_username, f'{db_id}-{LEGACY_ENTRY_KEY}', service=svc)
        assert authd is True
        assert p.code == pam.PAM_SUCCESS

        with fail_delay():
            # attempt to authenticate with invalid key should trigger a fail delay
            authd = p.authenticate(current_username, f'{db_id}-{LEGACY_ENTRY_KEY[0:-1]}', service=svc)
            assert authd is False
            assert p.code == pam.PAM_AUTH_ERR


def test_legacy_auth_admin_expired_key(current_username):
    """ Verify that an expired key results in PAM_AUTH_ERR """
    db_id = write_tdb_file(current_username, [LEGACY_ENTRY_HASH], True)
    with pam_service(admin_user=current_username) as svc:
        p = pam.pam()
        authd = p.authenticate(current_username, f'{db_id}-{LEGACY_ENTRY_KEY}', service=svc)
        assert authd is False
        assert p.code == pam.PAM_AUTH_ERR


def test_legacy_auth_non_admin(current_username):
    """ Test that legacy hash doesn't work for non-admin user
    We really want to deprecate these legacy keys.
    """
    write_tdb_file(current_username, [LEGACY_ENTRY_HASH])
    with pam_service() as svc:
        with fail_delay():
            p = pam.pam()
            authd = p.authenticate(current_username, LEGACY_ENTRY_KEY, service=svc)
            assert authd is False
            assert p.code == pam.PAM_AUTH_ERR


def test_legacy_auth_multiple_entries(current_username):
    """ verify last entry in hash list can be used to auth
    We allow multiple keys per user. Ensure that we can use more than the
    first key.
    """
    hashes = [crypto.generate_pbkdf2_512('canary') for i in range(0, 5)]
    hashes.append(LEGACY_ENTRY_HASH)

    db_id = write_tdb_file(current_username, hashes)
    with pam_service(admin_user=current_username) as svc:
        p = pam.pam()
        authd = p.authenticate(current_username, f'{db_id}-{LEGACY_ENTRY_KEY}', service=svc)
        assert authd is True
        assert p.code == pam.PAM_SUCCESS


def test_new_auth(current_username):
    """ verify that that new hash works as expected """
    key = crypto.generate_string(string_size=64)
    db_id = write_tdb_file(current_username, [crypto.generate_pbkdf2_512(key)])

    with pam_service() as svc:
        p = pam.pam()
        # verify that using correct key succeeds
        authd = p.authenticate(current_username, f'{db_id}-{key}', service=svc)
        assert authd is True
        assert p.code == pam.PAM_SUCCESS

        # verify that using incorrect key fails
        with fail_delay():
            authd = p.authenticate(current_username, f'{db_id}-{key[0:-1]}', service=svc)
            assert authd is False
            assert p.code == pam.PAM_AUTH_ERR


def test_new_auth_truncated_password(current_username):
    """ Verify that truncated password generates auth error """
    key = crypto.generate_string(string_size=64)
    db_id = write_tdb_file(current_username, [crypto.generate_pbkdf2_512(key)])

    with pam_service() as svc:
        p = pam.pam()
        with fail_delay():
            authd = p.authenticate(current_username, f'{db_id}-', service=svc)
            assert authd is False
            assert p.code == pam.PAM_AUTH_ERR


def test_new_auth_multi(current_username):
    """ verify that second key works with newer hash """
    key = crypto.generate_string(string_size=64)
    db_id = write_tdb_file(current_username, [
        LEGACY_ENTRY_HASH,
        crypto.generate_pbkdf2_512(key)
    ])
    with pam_service() as svc:
        p = pam.pam()
        # verify that using correct key succeeds
        authd = p.authenticate(current_username, f'{db_id}-{key}', service=svc)
        assert authd is True
        assert p.code == pam.PAM_SUCCESS

        # verify that using incorrect key fails
        with fail_delay():
            authd = p.authenticate(current_username, f'{db_id}-{key[0:-1]}', service=svc)
            assert authd is False
            assert p.code == pam.PAM_AUTH_ERR


def test_new_auth_timeout(current_username):
    """ verify that valid but expired key denies auth with expected error code """
    key = crypto.generate_string(string_size=64)
    db_id = write_tdb_file(current_username, [crypto.generate_pbkdf2_512(key)], True)
    with pam_service() as svc:
        p = pam.pam()
        with fail_delay():
            authd = p.authenticate(current_username, f'{db_id}-{key}', service=svc)
            assert authd is False
            assert p.code == pam.PAM_AUTH_ERR


def test_unsupported_service_file_name(current_username):
    """ pam_tdb has strict check that it can't be used for other services """
    key = crypto.generate_string(string_size=64)
    db_id = write_tdb_file(current_username, [crypto.generate_pbkdf2_512(key)])
    with pam_service(file_name='canary') as svc:
        p = pam.pam()
        # verify that using correct key succeeds
        authd = p.authenticate(current_username, f'{db_id}-{key}', service=svc)
        assert authd is False
        assert p.code == pam.PAM_SYSTEM_ERR


@pytest.mark.parametrize('thehash,pam_error', [
    (INVALID_HASH_TYPE, pam.PAM_AUTH_ERR),
    (INVALID_SALT, pam.PAM_AUTH_ERR),
    (INVALID_HASH, pam.PAM_AUTH_ERR),
    (MISSING_SALT, pam.PAM_AUTH_ERR),
    (MISSING_HASH, pam.PAM_AUTH_ERR),
    (EMPTY_HASH_STRING, pam.PAM_AUTHINFO_UNAVAIL),
])
def test_invalid_hash(current_username, thehash, pam_error):
    """ Check that variations of broken hash entries generate expected error """
    db_id = write_tdb_file(current_username, [thehash])
    with pam_service(admin_user=current_username) as svc:
        p = pam.pam()
        # verify that using correct key succeeds
        authd = p.authenticate(current_username, f'{db_id}-{LEGACY_ENTRY_KEY}', service=svc)
        assert authd is False
        assert p.code == pam_error


@pytest.mark.parametrize('fuzz_fn', [
    truncate_tdb_file,
    make_tdb_garbage,
    make_null_tdb_entry,
])
def test_invalid_tdb_data(current_username, fuzz_fn):
    """ verify we detect garbage tdb entry and flag for reinit"""
    key = crypto.generate_string(string_size=64)
    db_id = write_tdb_file(current_username, [crypto.generate_pbkdf2_512(key)], True)
    fuzz_fn(current_username)
    with pam_service() as svc:
        p = pam.pam()
        authd = p.authenticate(current_username, f'{db_id}-{key}', service=svc)
        assert authd is False
        assert p.code == pam.PAM_AUTHINFO_UNAVAIL
