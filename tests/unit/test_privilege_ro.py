# tests to validate behavior of becoming readonly. There are
# two parts to this
# 1 - the privilege set returned by auth.me should be changed
#   This is used by the webui and some internal checks in middleware
#
# 2 - the credential's allowlist used to authorize method calls should
#   also be changed. This is validated by checking the API response that
#   sensitive information is redacted.
from truenas_api_client import Client


def test__become_readonly_privilege_composition():
    with Client() as c:
        init_privilege = c.call('auth.me')['privilege']
        assert 'FULL_ADMIN' in init_privilege['roles']

        c.call('privilege.become_readonly')
        final_privilege = c.call('auth.me')['privilege']

        assert 'FULL_ADMIN' not in final_privilege['roles']
        for role in final_privilege['roles']:
            assert not role.endswith('_WRITE')


def test__become_readonly_redaction():
    with Client() as c:
        user_resp = c.call('user.query', [['username', '=', 'root']], {'get': True})
        assert user_resp['unixhash'] != '********'

        c.call('privilege.become_readonly')
        user_resp = c.call('user.query', [['username', '=', 'root']], {'get': True})
        assert user_resp['unixhash'] == '********'
