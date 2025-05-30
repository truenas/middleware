import errno
import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.utils import call


@pytest.fixture(scope="module")
def ipa_config():
    """ join then leave IPA domain so that we can evaluate server after leaving the IPA domain """
    with directoryservice('IPA') as config:
        ipa_config = config

    yield ipa_config


def test_cache_cleared(ipa_config):
    ipa_users_cnt = call('user.query', [['local', '=', False]], {'count': True})
    assert ipa_users_cnt == 0

    ipa_groups_cnt = call('group.query', [['local', '=', False]], {'count': True})
    assert ipa_groups_cnt == 0


@pytest.mark.parametrize('keytab_name', [
    'IPA_MACHINE_ACCOUNT',
    'IPA_NFS_KEYTAB',
    'IPA_SMB_KEYTAB'
])
def test_keytabs_deleted(ipa_config, keytab_name):
    kt = call('kerberos.keytab.query', [['name', '=', keytab_name]])
    assert len(kt) == 0


def test_check_no_kerberos_ticket(ipa_config):
    with pytest.raises(CallError) as ce:
        call('kerberos.check_ticket')

    assert ce.value.errno == errno.ENOKEY


def test_check_no_kerberos_realm(ipa_config):
    realms = call('kerberos.realm.query')
    assert len(realms) == 0, str(realms)


def test_system_keytab_has_no_nfs_principal(ipa_config):
    assert not call('kerberos.keytab.has_nfs_principal')


def test_smb_keytab_does_not_exist(ipa_config):
    with pytest.raises(CallError) as ce:
        call('filesystem.stat', '/etc/ipa/smb.keytab')

    assert ce.value.errno == errno.ENOENT


def test_no_admin_privilege(ipa_config):
    configuration = ipa_config['config']['configuration']
    priv = call('privilege.query', [['name', '=', configuration['domain'].upper()]])
    assert priv == []


def test_no_certificate(ipa_config):
    certs = call('certificate.query', [['name', '=', 'IPA_DOMAIN_CACERT']])
    assert len(certs) == 0, str(certs)


def test_no_dns_resolution(ipa_config):
    try:
        results = call('dnsclient.forward_lookup', {'names': [ipa_config['host']]})
        assert len(results) == 0
    except Exception:
        pass
