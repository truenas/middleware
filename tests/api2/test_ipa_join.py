import pytest
from middlewared.test.integration.assets.directory_service import ipa, override_nameservers
from middlewared.test.integration.utils import call


@pytest.fixture(scope="module")
def do_freeipa_connection():
    with ipa() as config:
        yield config


def test_setup_and_enabling_freeipa(do_freeipa_connection):
    config = do_freeipa_connection

    ds = call('directoryservices.status')
    assert ds['type'] == 'IPA'
    assert ds['status'] == 'HEALTHY'

    alerts = call('alert.list')
    # There's a one-shot alert that gets fired if we are an IPA domain
    # connected via legacy mechanism.
    assert len(alerts) == 0, str(alerts)

    assert config['kerberos_realm'], str(config)
    assert config['kerberos_principal'], str(config)

    # our kerberos principal should be the host one (not SMB or NFS)
    assert config['kerberos_principal'].startswith('host/')


@pytest.mark.parametrize('keytab_name', [
    'IPA_MACHINE_ACCOUNT',
    'IPA_NFS_KEYTAB',
    'IPA_SMB_KEYTAB'
])
def test_keytabs_exist(do_freeipa_connection, keytab_name):
    call('kerberos.keytab.query', [['name', '=', keytab_name]], {'get': True})


def test_check_kerberos_ticket(do_freeipa_connection):
    tkt = call('kerberos.check_ticket')

    assert tkt['name_type'] == 'KERBEROS_PRINCIPAL'
    assert tkt['name'].startswith(do_freeipa_connection['kerberos_principal'])


def test_system_keytab_has_nfs_principal(do_freeipa_connection):
    assert call('kerberos.keytab.has_nfs_principal')


def test_smb_keytab_exists(do_freeipa_connection):
    call('filesystem.stat', '/etc/ipa/smb.keytab')
