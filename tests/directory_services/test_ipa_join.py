import pytest

from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.assets.product import product_type
from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.client import truenas_server
from truenas_api_client import ClientException


@pytest.fixture(scope="module")
def do_freeipa_connection():
    with directoryservice('IPA') as config:
        yield config


@pytest.fixture(scope="function")
def override_product():
    if truenas_server.server_type == 'ENTERPRISE_HA':
        yield
    else:
        with product_type():
            yield


@pytest.fixture(scope="function")
def enable_ds_auth(override_product):
    sys_config = call('system.general.update', {'ds_auth': True})
    try:
        yield sys_config
    finally:
        call('system.general.update', {'ds_auth': False})


def test_setup_and_enabling_freeipa(do_freeipa_connection):
    config = do_freeipa_connection['config']

    ds = call('directoryservices.status')
    assert ds['type'] == 'IPA'
    assert ds['status'] == 'HEALTHY'

    assert config['kerberos_realm'], str(config)
    assert config['credential']['credential_type'] == 'KERBEROS_PRINCIPAL'
    assert config['credential']['principal'], str(config)

    # our kerberos principal should be the host one (not SMB or NFS)
    assert config['credential']['principal'].startswith('host/')


def test_accounts_cache(do_freeipa_connection):
    ipa_users_cnt = call('user.query', [['local', '=', False]], {'count': True})
    assert ipa_users_cnt != 0

    ipa_groups_cnt = call('group.query', [['local', '=', False]], {'count': True})
    assert ipa_groups_cnt != 0


@pytest.mark.parametrize('keytab_name', [
    'IPA_MACHINE_ACCOUNT',
    'IPA_NFS_KEYTAB',
    'IPA_SMB_KEYTAB'
])
def test_keytabs_exist(do_freeipa_connection, keytab_name):
    call('kerberos.keytab.query', [['name', '=', keytab_name]], {'get': True})


def test_check_kerberos_ticket(do_freeipa_connection):
    config = do_freeipa_connection['config']
    assert config['credential']['credential_type'] == 'KERBEROS_PRINCIPAL'
    tkt = call('kerberos.check_ticket')

    assert tkt['name_type'] == 'KERBEROS_PRINCIPAL'
    assert tkt['name'].startswith(config['credential']['principal'])


def test_certificate(do_freeipa_connection):
    call('certificate.query', [['name', '=', 'IPA_DOMAIN_CACERT']], {'get': True})


def test_system_keytab_has_nfs_principal(do_freeipa_connection):
    assert call('kerberos.keytab.has_nfs_principal')


def test_smb_keytab_exists(do_freeipa_connection):
    call('filesystem.stat', '/etc/ipa/smb.keytab')


def test_admin_privilege(do_freeipa_connection, enable_ds_auth):
    ipa_config = do_freeipa_connection['config']
    account = do_freeipa_connection['account']

    priv_names = [priv['name'] for priv in call('privilege.query')]
    assert ipa_config['configuration']['domain'].upper() in priv_names

    priv = call('privilege.query', [['name', '=', ipa_config['configuration']['domain'].upper()]], {'get': True})
    admins_grp = call('group.get_group_obj', {'groupname': 'admins', 'sid_info': True})

    assert len(priv['ds_groups']) == 1
    assert priv['ds_groups'][0]['gid'] == admins_grp['gr_gid']
    assert priv['ds_groups'][0]['sid'] == admins_grp['sid']

    assert priv['roles'] == ['FULL_ADMIN']

    with client(auth=(account.username, account.password)) as c:
        me = c.call('auth.me')

        assert 'DIRECTORY_SERVICE' in me['account_attributes']
        assert 'IPA' in me['account_attributes']
        assert 'FULL_ADMIN' in me['privilege']['roles']


def test_dns_resolution(do_freeipa_connection):
    ipa_config = do_freeipa_connection['config']['configuration']
    fqdn = f'{ipa_config["hostname"]}.{ipa_config["domain"]}'

    addresses = call('dnsclient.forward_lookup', {'names': [fqdn]})
    assert len(addresses) != 0


def test_ipa_config_recover(do_freeipa_connection):
    """ Remove the default config and verify our health check restores it """
    ssh('rm /etc/ipa/default.conf')
    with pytest.raises(ClientException, match="IPA default.conf file is missing"):
        call('directoryservices.health.check')

    call('directoryservices.health.recover')
    st = call('directoryservices.status')
    assert st['status'] == 'HEALTHY'
