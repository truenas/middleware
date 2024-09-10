import pytest

from middlewared.test.integration.utils import call

try:
    from config import (
        LDAPBASEDN,
        LDAPBINDDN,
        LDAPBINDPASSWORD,
        LDAPHOSTNAME,
    )
except ImportError:
    Reason = 'LDAP* variable are not setup in config.py'
    # comment pytestmark for development testing with --dev-test
    pytestmark = pytest.mark.skipif(True, reason=Reason)


def test_create_and_delete_idmap_certificate():
    payload = {
        'name': 'BOB.NB',
        'range_low': 1000,
        'range_high': 2000,
        'certificate': 1,
        'idmap_backend': 'RFC2307',
        'options': {
            'ldap_server': 'STANDALONE',
            'bind_path_user': LDAPBASEDN,
            'bind_path_group': LDAPBASEDN,
            'ldap_url': LDAPHOSTNAME,
            'ldap_user_dn': LDAPBINDDN,
            'ldap_user_dn_password': LDAPBINDPASSWORD,
            'ssl': 'ON',
            'ldap_realm': False,
        }
    }
    idmap_id = call('idmap.create', payload)['id']

    call('idmap.delete', idmap_id)
    assert call('idmap.query', [['id', '=', idmap_id]]) == []
