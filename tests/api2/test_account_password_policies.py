import pytest
import secrets
import string

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user
from middlewared.test.integration.utils import call, client, ssh

USER = 'testpasswduser'
GROUP = 'testpasswdgroup'
PASSWD2 = 'Testpassw0rd2'
PASSWD3 = 'Testpassw0rd3'
PASSWD4 = 'Testpassw0rd4'

PASSWORD_REUSE_ERR = """
Security configuration for this user account requires a password that does not match any of the last 10 passwords.
"""

@pytest.fixture(scope="module")
def create_unprivileged_user(request):
    with unprivileged_user(
        username=USER,
        group_name=GROUP,
        privilege_name='TEST_PASSWORD_POLICY',
        roles=['READONLY'],
        allowlist=[],
        web_shell=False
    ) as u:
        yield u


def test_password_reset(request, create_unprivileged_user):
    u = call(
        'user.query',
        [['username', '=', create_unprivileged_user.username]],
        {'get': True}
    )

    call('user.update', u['id'], {
        'shell': '/usr/bin/bash',
        'ssh_password_enabled': True,
        'password_aging_enabled': True
    })
    PASSWD1 = create_unprivileged_user.password

    ssh('pwd', user=USER, password=PASSWD1)

    # `user.set_password` should be allowed
    with client(auth=(USER, PASSWD1)) as c:
        c.call('user.set_password', {'username': USER, 'old_password': PASSWD1, 'new_password': PASSWD2})

    # Check that shadow file is updated properly
    ssh('pwd', user=USER, password=PASSWD2)

    with client(auth=(USER, PASSWD2)) as c:
        # Reusing password should raise ValidationError
        with pytest.raises(ValidationErrors) as ve:
            c.call('user.set_password', {'username': USER, 'old_password': PASSWD2, 'new_password': PASSWD1})

        assert PASSWORD_REUSE_ERR in str(ve), str(ve)

    # Disabling password aging should allow reuse
    call('user.update', u['id'], {'password_aging_enabled': False})
    with client(auth=(USER, PASSWD2)) as c:
        c.call('user.set_password', {'username': USER, 'old_password': PASSWD2, 'new_password': PASSWD1})

    call('user.update', u['id'], {
        'password_aging_enabled': True,
        'must_change_password': True,
    })
    with client(auth=(USER, PASSWD1)) as c:
        # Verify that setting password removes `must_change_password` flag.
        assert c.call('auth.me')['password_change_required']
        c.call('user.set_password', {'username': USER, 'old_password': PASSWD1, 'new_password': PASSWD2})
        assert c.call('auth.me')['password_change_required'] is False

        call('user.update', u['id'], {'min_password_age': 1})

        # This should fail since it violates minimum password age
        # requirement
        with pytest.raises(ValidationErrors) as ve:
            c.call('user.set_password', {'username': USER, 'old_password': PASSWD2, 'new_password': PASSWD3})

        call('user.update', u['id'], {'min_password_age': 0})
        c.call('user.set_password', {'username': USER, 'old_password': PASSWD2, 'new_password': PASSWD3})
