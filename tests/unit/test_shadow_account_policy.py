import pytest

from contextlib import contextmanager
from datetime import datetime, timedelta, UTC
from middlewared.utils.security import (
    check_password_complexity,
    PasswordComplexity,
)
from middlewared.utils.time_utils import datetime_to_epoch_days
from truenas_api_client import Client

OLD_DATE = 1711547527
OLD_DATETIME = datetime.fromtimestamp(OLD_DATE, UTC)
TEST_HISTORY = 5  # validate 5 generations of passwords
SEVEN_DAYS_AGO = int((datetime.now(UTC) - timedelta(days=7)).timestamp())


@pytest.fixture(scope='module')
def set_fips_available():
    with Client() as c:
        c.call('test.set_mock', 'system.security.info.fips_available', None, {'return_value': True})

    try:
        yield
    finally:
        with Client() as c:
            c.call('test.remove_mock', 'system.security.info.fips_available', None)


@contextmanager
def security_config(**kwargs):
    with Client() as c:
        old = c.call('system.security.config')
        old.pop('id')
        new = c.call('system.security.update', kwargs, job=True)
        try:
            yield new

        finally:
            c.call('system.security.update', old, job=True)


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


@contextmanager
def create_old_user(name, **kwargs):
    with create_user(name, **kwargs) as u:
        with Client() as c:
            c.call('datastore.update', 'account.bsdusers', u['id'], {'bsdusr_last_password_change': OLD_DATE})
            c.call('etc.generate', 'shadow')
            yield c.call('user.get_instance', u['id']) | {'password': u['password']}


@pytest.fixture(scope='function')
def old_admin():
    with create_old_user('old_admin_user') as u:
        with Client() as c:
            ba_id = c.call('group.query', [['name', '=', 'builtin_administrators']], {'get': True})['id']
            c.call('user.update', u['id'], {'groups': u['groups'] + [ba_id]})
            yield u


def get_shadow_entry(username):
    entry_str = None
    with open('/etc/shadow', 'r') as f:
        for line in f:
            if line.startswith(f'{username}:'):
                entry_str = line
                break

    assert entry_str is not None

    name, pwd, chg, min_age, max_age, warning, inactive, expiration, reserved = entry_str.split(':')
    return {
        'name': name,
        'unixhash': pwd,
        'lastchange': int(chg),
        'min_password_age': int(min_age) if min_age else None,
        'max_password_age': int(max_age) if max_age else None,
        'password_warn_period': int(warning) if warning else None,
        'password_inactivity_period': int(inactive) if inactive else None,
        'expiration': int(expiration) if expiration else None,
    }


@pytest.fixture(scope='module')
def password_history():
    with Client() as c:
        c.call('system.security.update', {
            'min_password_age': None,
            'max_password_age': None,
            'password_history_length': TEST_HISTORY
        }, job=True)

    try:
        yield
    finally:
        with Client() as c:
            c.call('system.security.update', {
                'min_password_age': None,
                'max_password_age': None,
                'password_history_length': None
            }, job=True)


def test__new_user_password_change_date():
    """ This test covers basic shadow file fields and verifies that they are written correctly """
    with create_user('test_user') as u:
        shadow = get_shadow_entry(u['username'])
        assert shadow['name'] == u['username']
        assert shadow['unixhash'] == u['unixhash']
        assert shadow['lastchange'] == datetime_to_epoch_days(u['last_password_change'])
        assert shadow['expiration'] is None


def test__update_user_password():
    """ This test verifies that updating password changes the last change date for the shadow file """
    with create_old_user('test_user') as u:
        shadow = get_shadow_entry(u['username'])
        assert shadow['name'] == u['username']
        assert shadow['unixhash'] == u['unixhash']
        assert shadow['lastchange'] == datetime_to_epoch_days(OLD_DATETIME)
        assert shadow['expiration'] is None

        with Client() as c:
            u2 = c.call('user.update', u['id'], {'password': 'Test1234'})

        shadow = get_shadow_entry(u['username'])
        assert shadow['name'] == u2['username']
        assert shadow['unixhash'] == u2['unixhash']
        assert shadow['lastchange'] != datetime_to_epoch_days(OLD_DATETIME)
        assert shadow['expiration'] is None


@pytest.mark.parametrize('sec,value', (
    ('min_password_age', 10),
    ('max_password_age', 10),
    ('password_history_length', 5),
    ('min_password_length', 50),
    ('password_complexity_ruleset', {PasswordComplexity.UPPER}),
))
def test__licensing(sec, value):
    with Client() as c:
        with pytest.raises(Exception, match='This feature can only be enabled on licensed'):
            c.call('system.security.update', {sec: value}, job=True)


@pytest.mark.parametrize('ruleset,password,expected', (
    ({PasswordComplexity.UPPER}, 'A', set()),  # Latin upper should succeed
    ({PasswordComplexity.UPPER}, 'Г', set()),  # Cyrillic upper should succeed
    ({PasswordComplexity.UPPER}, 'a', {PasswordComplexity.UPPER}),  # Latin lower should fail
    ({PasswordComplexity.UPPER}, 'г', {PasswordComplexity.UPPER}),  # Cyrillic lower should fail
    ({PasswordComplexity.LOWER}, 'A', {PasswordComplexity.LOWER}),
    ({PasswordComplexity.LOWER}, 'Г', {PasswordComplexity.LOWER}),
    ({PasswordComplexity.LOWER}, 'a', set()),
    ({PasswordComplexity.LOWER}, 'г', set()),
    ({PasswordComplexity.LOWER, PasswordComplexity.UPPER}, 'A', {PasswordComplexity.LOWER}),
    ({PasswordComplexity.LOWER, PasswordComplexity.UPPER}, 'Г', {PasswordComplexity.LOWER}),
    ({PasswordComplexity.LOWER, PasswordComplexity.UPPER}, 'Aa', set()),
    ({PasswordComplexity.LOWER, PasswordComplexity.UPPER}, 'Гг', set()),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER},
        'A',
        {PasswordComplexity.LOWER, PasswordComplexity.NUMBER}
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER},
        'Г',
        {PasswordComplexity.LOWER, PasswordComplexity.NUMBER}
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER},
        'Aa',
        {PasswordComplexity.NUMBER}
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER},
        'Гг',
        {PasswordComplexity.NUMBER}
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER},
        'Aa1',
        set()
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER},
        'Гг1',
        set()
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER, PasswordComplexity.SPECIAL},
        'A',
        {PasswordComplexity.LOWER, PasswordComplexity.NUMBER, PasswordComplexity.SPECIAL}
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER, PasswordComplexity.SPECIAL},
        'Г',
        {PasswordComplexity.LOWER, PasswordComplexity.NUMBER, PasswordComplexity.SPECIAL}
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER, PasswordComplexity.SPECIAL},
        'Aa',
        {PasswordComplexity.NUMBER, PasswordComplexity.SPECIAL}
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER, PasswordComplexity.SPECIAL},
        'Гг',
        {PasswordComplexity.NUMBER, PasswordComplexity.SPECIAL}
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER, PasswordComplexity.SPECIAL},
        'Aa1',
        {PasswordComplexity.SPECIAL}
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER, PasswordComplexity.SPECIAL},
        'Гг1',
        {PasswordComplexity.SPECIAL}
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER, PasswordComplexity.SPECIAL},
        'Aa1!',
        set()
    ),
    (
        {PasswordComplexity.LOWER, PasswordComplexity.UPPER, PasswordComplexity.NUMBER, PasswordComplexity.SPECIAL},
        'Гг1!',
        set()
    ),
))
def test__password_complexity(ruleset, password, expected, set_fips_available):
    """ Make sure password deficiencies are properly identified """
    assert check_password_complexity(ruleset, password) == expected


@pytest.mark.parametrize('sec', (
    {
        'min_password_age': 10,
        'max_password_age': None,
    },
    {
        'min_password_age': None,
        'max_password_age': 60,
    },
    {
        'min_password_age': None,
        'max_password_age': None,
    },
))
def test__account_policy_shadow_file(sec, set_fips_available):
    """ Verify that system security account settings properly modify shadow file """
    with Client() as c:
        c.call('system.security.update', sec, job=True)

    with create_user('test_user_policy') as u:
        shadow = get_shadow_entry(u['username'])
        for key, value in sec.items():
            assert shadow[key] == value


# NOTE: this can be expanded when middleware has more comprensive PAM plumbing
# to allow password resets / expose shadow warning and inactive fields


@pytest.mark.parametrize('sec,error', (
    ({
        'min_password_age': 25,
        'max_password_age': 10,
    }, 'Minimum password age must be lower than the maximum password age'),
))
def test__account_policy_validation(sec, error, set_fips_available):
    with Client() as c:
        with pytest.raises(Exception, match=error):
            c.call('system.security.update', sec, job=True)


def test__password_history(password_history):
    """ Verify that password history is properly applied """
    with create_user('history_user', random_password=False, password='Canary') as u:
        with Client() as c:
            with pytest.raises(Exception, match='requires a password that does not match'):
                c.call('user.update', u['id'], {'password': 'Canary'})

            for i in range(0, TEST_HISTORY):
                c.call('user.update', u['id'], {'password': f'Canary{i}'})

            # We've cycled through history and should be OK again
            c.call('user.update', u['id'], {'password': 'Canary'})


def test__password_expired(old_admin):
    """ Verify that expired password gives EXPIRED response type """
    with Client('ws://127.0.0.1/api/current') as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': old_admin['username'],
            'password': old_admin['password']
        })
        assert resp['response_type'] == 'SUCCESS'

    with security_config(max_password_age=60):
        with Client() as c:
            user = c.call('user.get_instance', old_admin['id'])
            assert user['password_change_required']

        with Client('ws://127.0.0.1/api/current') as c:
            resp = c.call('auth.login_ex', {
                'mechanism': 'PASSWORD_PLAIN',
                'username': old_admin['username'],
                'password': old_admin['password']
            })
            assert resp['response_type'] == 'EXPIRED'


def test__password_expiry_warning(old_admin):
    """ Verify that account attributes show PASSWORD_CHANGE_REQUIRED """
    with Client('ws://127.0.0.1/api/current') as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': old_admin['username'],
            'password': old_admin['password']
        })
        assert resp['response_type'] == 'SUCCESS'

    with security_config(max_password_age=10) as sec:
        with Client() as c:
            c.call('datastore.update', 'account.bsdusers', old_admin['id'], {
                'bsdusr_last_password_change': SEVEN_DAYS_AGO
            })
            c.call('etc.generate', 'shadow')
            user = c.call('user.get_instance', old_admin['id'])
            assert user['password_change_required'], str({"user": user, "sec": sec})

        with Client('ws://127.0.0.1/api/current') as c:
            resp = c.call('auth.login_ex', {
                'mechanism': 'PASSWORD_PLAIN',
                'username': old_admin['username'],
                'password': old_admin['password']
            })
            assert resp['response_type'] == 'SUCCESS', str(get_shadow_entry(user['username']))
            assert 'PASSWORD_CHANGE_REQUIRED' in resp['user_info']['account_attributes']


def test__password_length(old_admin):
    with security_config(min_password_length=8):
        with Client() as c:
            # Creating new user with short password should fail
            with pytest.raises(Exception, match='The specified password is too short'):
                with create_user('short_password', random_password=False, password='Cats'):
                    pass

            # Updating user with new password should fail
            with pytest.raises(Exception, match='The specified password is too short'):
                c.call('user.update', old_admin['id'], {'password': 'Cats'})

            # Using password reset API should also fail
            with pytest.raises(Exception, match='The specified password is too short'):
                c.call('user.set_password', {'username': old_admin['username'], 'new_password': 'Cats'})
