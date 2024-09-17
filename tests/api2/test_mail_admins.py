import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import call

MAILUSER = 'wilbur'
MAILADDR = 'wilbur.spam@ixsystems.com'
NONMAIL_USER = 'wilburette'
NONMAIL_ADDR = 'wilburette.spam@ixsystems.com'
PASSWD = 'abcd1234'


@pytest.fixture(scope='module')
def full_admin_user():
    ba_id = call('group.query', [['gid', '=', 544]], {'get': True})['id']
    with user({
        'username': NONMAIL_USER,
        'full_name': NONMAIL_USER,
        'group_create': True,
        'email': NONMAIL_ADDR,
        'password': PASSWD
    }, get_instance=False):
        with user({
            'username': MAILUSER,
            'full_name': MAILUSER,
            'group_create': False,
            'email': MAILADDR,
            'group': ba_id,
            'password': PASSWD
        }, get_instance=True) as u:
            yield u


def test_mail_administrators(full_admin_user):
    emails = call('mail.local_administrators_emails')
    assert MAILADDR in emails
    assert NONMAIL_ADDR not in emails
