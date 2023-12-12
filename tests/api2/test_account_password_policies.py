import pytest
import secrets
import string

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import call, client, ssh


USER = 'password_reset_user'
PASSWD1 = 'Testpassw0rd1'
PASSWD2 = 'Testpassw0rd2'
PASSWD3 = 'Testpassw0rd3'

PASSWORD_REUSE_ERR = """
Security configuration for this user account requires a password that does not match any of the last 10 passwords.
"""

def test_password_reset(grant_users_password_reset_privilege):
    with user({
        'username': USER,
        'full_name': USER,
        'home': '/var/empty',
        'shell': '/usr/bin/bash',
        'password_aging_enabled': True,
        'ssh_password_enabled': True,
        'password': PASSWD1
    }) as u:
        ssh('pwd', user=USER, password=PASSWD1)

        # `user.set_password` should be allowed
        with client(auth=(USER, PASSWD1)) as c:
            c.call('user.set_password', PASSWD1, PASSWD2)

        # Check that shadow file is updated properly
        ssh('pwd', user=USER, password=PASSWD2)

        with client(auth=(USER, PASSWD2)) as c:
            # Reusing password should raise ValidationError
            with pytest.raises(ValidationErrors) as ve:
                c.call('user.set_password', PASSWD2, PASSWD1)

            assert PASSWORD_REUSE_ERR in str(ve), str(ve)

        # Disabling password aging should allow reuse
        call('user.update', u['id'], {'password_aging_enabled': False})
        with client(auth=(USER, PASSWD2)) as c:
            c.call('user.set_password', PASSWD2, PASSWD1)

        call('user.update', u['id'], {
            'password_aging_enabled': True,
            'must_change_password': True,
        })
        with client(auth=(USER, PASSWD1)) as c:
            # Verify that setting password removes `must_change_password` flag.
            assert c.call('auth.me')['password_change_required']
            c.call('user.set_password', PASSWD1, PASSWD2)
            assert c.call('auth.me')['password_change_required'] is False

            call('user.update u['id'], {'min_password_age': 1})

            # This should fail since it violates minimum password age
            # requirement
            with pytest.raises(ValidationErrors) as ve:
                c.call('user.set_password', PASSWD2, PASSWD3)

            call('user.update u['id'], {'min_password_age': 0})
            c.call('user.set_password', PASSWD2, PASSWD3)
