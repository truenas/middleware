import contextlib
import datetime
import secrets
import string
import time

import pytest

from auto_config import pool_name
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.time_utils import utc_now

EVENT_KEYS = {
    'address',
    'audit_id',
    'event',
    'event_data',
    'message_timestamp',
    'service',
    'service_data',
    'session',
    'success',
    'timestamp',
    'username'
}
ACCEPT_KEYS = {
    'columns',
    'command',
    'lines',
    'runargv',
    'runcwd',
    'runenv',
    'runuid',
    'runuser',
    'server_time',
    'source',
    'submit_time',
    'submitcwd',
    'submitenv',
    'submithost',
    'submituser',
    'uuid'
}
REJECT_KEYS = {
    'columns',
    'command',
    'lines',
    'reason',
    'runargv',
    'runcwd',
    'runuid',
    'runuser',
    'server_time',
    'submit_time',
    'submitcwd',
    'submitenv',
    'submithost',
    'submituser',
    'uuid'
}

LS_COMMAND = '/bin/ls'
ECHO_COMMAND = '/bin/echo'

SUDO_TO_USER = 'sudo-to-user'
SUDO_TO_PASSWORD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))


def get_utc():
    utc_time = int(utc_now().replace(tzinfo=datetime.timezone.utc).timestamp())
    return utc_time


def user_sudo_events(username, count=False):
    payload = {
        'services': ['SUDO'],
        'query-filters': [['username', '=', username]],
    }
    if count:
        payload['query-options'] = {'count': True}
    else:
        payload['query-options'] = {'limit': 1000}

    return call('audit.query', payload)


def wait_for_events(username, newcount, retries=20, delay=0.5):
    assert retries > 0 and retries <= 20
    assert delay >= 0.1 and delay <= 1
    while newcount != user_sudo_events(username, True) and retries:
        time.sleep(delay)
        retries -= 1
    return newcount


def assert_accept(event):
    assert type(event) is dict
    set(event.keys()) == EVENT_KEYS
    assert set(event['event_data'].keys()) == {'sudo'}
    assert set(event['event_data']['sudo'].keys()) == {'accept'}
    assert set(event['event_data']['sudo']['accept'].keys()) == ACCEPT_KEYS
    return event['event_data']['sudo']['accept']


def assert_reject(event):
    assert type(event) is dict
    set(event.keys()) == EVENT_KEYS
    assert set(event['event_data'].keys()) == {'sudo'}
    assert set(event['event_data']['sudo'].keys()) == {'reject'}
    assert set(event['event_data']['sudo']['reject'].keys()) == REJECT_KEYS
    return event['event_data']['sudo']['reject']


def assert_timestamp(event, event_data):
    """
    NAS-130373:  message_timestamp should be UTC
    """
    assert type(event) is dict
    submit_time = event_data['submit_time']['seconds']
    msg_ts = event['message_timestamp']
    utc_ts = get_utc()

    # Confirm consistency and correctness of timestamps.
    # The message_timestamp and the submit_time should be UTC and
    # are expected to be mostly the same value. We allow for a generous delta between
    # current UTC and the audit message timestamps.
    assert abs(utc_ts - msg_ts) < 5, f"utc_ts={utc_ts}, msg_ts={msg_ts}"
    assert abs(utc_ts - int(submit_time)) < 5, f"utc_ts={utc_ts}, submit_time={submit_time}"
    assert abs(msg_ts - int(submit_time)) < 5, f"msg_ts={msg_ts}, submit_time={submit_time}"


@contextlib.contextmanager
def initialize_for_sudo_tests(username, password, data):
    data.update({
        'username': username,
        'full_name': username,
        'group_create': True,
        'home': f'/mnt/{pool_name}',
        'password': password,
        'shell': '/usr/bin/bash',
        'ssh_password_enabled': True,
    })
    with user(data) as newuser:
        yield newuser


@pytest.fixture(scope='module')
def sudo_to_user():
    with initialize_for_sudo_tests(SUDO_TO_USER, SUDO_TO_PASSWORD, {}) as u:
        yield u


class SudoTests:

    def generate_command(self, cmd, runuser=None, password=None):
        command = ['sudo']
        if password:
            command.append('-S')
        if runuser:
            command.extend(['-u', runuser])
        command.append(cmd)
        return " ".join(command)

    def to_list(self, value):
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            return value.split(',')
        else:
            raise ValueError("Unsupported value type", value)

    def allowed_all(self):
        """All of the sudo commands are allowed"""
        # First get a baseline # of events
        count = user_sudo_events(self.USER, True)

        # Now create an event and do some basic checking
        self.sudo_command('ls /etc')
        assert count + 1 == wait_for_events(self.USER, count + 1)
        event = user_sudo_events(self.USER)[-1]
        accept = assert_accept(event)
        assert accept['submituser'] == self.USER
        assert accept['command'] == LS_COMMAND
        assert accept['runuser'] == 'root'
        assert self.to_list(accept['runargv']) == ['ls', '/etc']
        # NAS-130373
        assert_timestamp(event, accept)

        # One more completely unique command
        magic = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(20))
        self.sudo_command(f'echo {magic}')
        assert count + 2 == wait_for_events(self.USER, count + 2)
        accept = assert_accept(user_sudo_events(self.USER)[-1])
        assert accept['submituser'] == self.USER
        assert accept['command'] == ECHO_COMMAND
        assert accept['runuser'] == 'root'
        assert self.to_list(accept['runargv']) == ['echo', magic]

        # sudo to a non-root user
        self.sudo_command('ls /tmp', SUDO_TO_USER)
        assert count + 3 == wait_for_events(self.USER, count + 3)
        accept = assert_accept(user_sudo_events(self.USER)[-1])
        assert accept['submituser'] == self.USER
        assert accept['command'] == LS_COMMAND
        assert accept['runuser'] == SUDO_TO_USER
        assert self.to_list(accept['runargv']) == ['ls', '/tmp']

    def allowed_some(self):
        """Some of the sudo commands are allowed"""
        # First get a baseline # of events
        count = user_sudo_events(self.USER, True)

        # Generate a sudo command that we ARE allowed perform
        magic = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(20))
        self.sudo_command(f'echo {magic}')
        assert count + 1 == wait_for_events(self.USER, count + 1)
        accept = assert_accept(user_sudo_events(self.USER)[-1])
        assert accept['submituser'] == self.USER
        assert accept['command'] == ECHO_COMMAND
        assert accept['runuser'] == 'root'
        assert self.to_list(accept['runargv']) == ['echo', magic]

        # Generate a sudo command that we are NOT allowed perform
        with pytest.raises(AssertionError):
            self.sudo_command('ls /etc')
        # Returned exception depends upon whether passwd or nopasswd
        assert count + 2 == wait_for_events(self.USER, count + 2)
        reject = assert_reject(user_sudo_events(self.USER)[-1])
        assert reject['submituser'] == self.USER
        assert reject['command'] == LS_COMMAND
        assert reject['runuser'] == 'root'
        assert self.to_list(reject['runargv']) == ['ls', '/etc']
        assert reject['reason'] == 'command not allowed'

    def allowed_none(self):
        """None of the sudo commands are allowed"""
        # First get a baseline # of events
        count = user_sudo_events(self.USER, True)

        # Now create an event and do some basic checking to ensure it failed
        with pytest.raises(AssertionError) as ve:
            self.sudo_command('ls /etc')
        assert f'{self.USER} is not in the sudoers file.' in str(ve), str(ve)
        assert count + 1 == wait_for_events(self.USER, count + 1)
        event = user_sudo_events(self.USER)[-1]
        reject = assert_reject(event)
        assert reject['submituser'] == self.USER
        assert reject['command'] == LS_COMMAND
        assert reject['runuser'] == 'root'
        assert self.to_list(reject['runargv']) == ['ls', '/etc']
        assert reject['reason'] == 'user NOT in sudoers'
        # NAS-130373
        assert_timestamp(event, reject)


class SudoNoPasswd:
    def sudo_command(self, cmd, runuser=None):
        command = self.generate_command(cmd, runuser)
        ssh(command, user=self.USER, password=self.PASSWORD)


class SudoPasswd:
    def sudo_command(self, cmd, runuser=None):
        command = f'echo {self.PASSWORD} | {self.generate_command(cmd, runuser, self.PASSWORD)}'
        ssh(command, user=self.USER, password=self.PASSWORD)


class TestSudoAllowedAllNoPasswd(SudoTests, SudoNoPasswd):

    USER = 'sudo-allowed-all-nopw-user'
    PASSWORD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))

    @pytest.fixture(scope='class')
    def create_user(self):
        with initialize_for_sudo_tests(self.USER,
                                       self.PASSWORD,
                                       {'sudo_commands_nopasswd': ['ALL']}) as u:
            yield u

    def test_audit_query(self, sudo_to_user, create_user):
        self.allowed_all()


class TestSudoAllowedAllPasswd(SudoTests, SudoPasswd):

    USER = 'sudo-allowed-all-pw-user'
    PASSWORD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))

    @pytest.fixture(scope='class')
    def create_user(self):
        with initialize_for_sudo_tests(self.USER,
                                       self.PASSWORD,
                                       {'sudo_commands': ['ALL']}) as u:
            yield u

    def test_audit_query(self, sudo_to_user, create_user):
        self.allowed_all()


class TestSudoAllowedNonePasswd(SudoTests, SudoPasswd):

    USER = 'sudo-allowed-none-pw-user'
    PASSWORD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))

    @pytest.fixture(scope='class')
    def create_user(self):
        with initialize_for_sudo_tests(self.USER, self.PASSWORD, {}) as u:
            yield u

    def test_audit_query(self, create_user):
        self.allowed_none()


class TestSudoAllowedSomeNoPasswd(SudoTests, SudoNoPasswd):

    USER = 'sudo-allowed-some-nopw-user'
    PASSWORD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))

    @pytest.fixture(scope='class')
    def create_user(self):
        with initialize_for_sudo_tests(self.USER,
                                       self.PASSWORD,
                                       {'sudo_commands_nopasswd': [ECHO_COMMAND]}) as u:
            yield u

    def test_audit_query(self, create_user):
        self.allowed_some()


class TestSudoAllowedSomePasswd(SudoTests, SudoPasswd):

    USER = 'sudo-allowed-some-pw-user'
    PASSWORD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))

    @pytest.fixture(scope='class')
    def create_user(self):
        with initialize_for_sudo_tests(self.USER,
                                       self.PASSWORD,
                                       {'sudo_commands': [ECHO_COMMAND]}) as u:
            yield u

    def test_audit_query(self, create_user):
        self.allowed_some()
