import ipaddress
import os
from time import sleep

import dns.resolver
import pytest
from truenas_api_client import \
    ValidationErrors as ClientValidationErrors
from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.directory_service import (
    active_directory, override_nameservers)
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.assets.product import product_type
from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils.system import reset_systemd_svcs
from pytest_dependency import depends

from auto_config import ha
from protocols import smb_connection, smb_share

if ha and "hostname_virtual" in os.environ:
    hostname = os.environ["hostname_virtual"]
else:
    from auto_config import hostname

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME
    AD_USER = fr"AD02\{ADUSERNAME.lower()}"
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)


SMB_NAME = "TestADShare"


def remove_dns_entries(payload):
    call('dns.nsupdate', {'ops': payload})


def cleanup_forward_zone():
    try:
        result = call('dnsclient.forward_lookup', {'names': [f'{hostname}.{AD_DOMAIN}']})
    except dns.resolver.NXDOMAIN:
        # No entry, nothing to do
        return

    ips_to_remove = [rdata['address'] for rdata in result]

    payload = []
    for i in ips_to_remove:
        addr = ipaddress.ip_address(i)
        payload.append({
            'command': 'DELETE',
            'name': f'{hostname}.{AD_DOMAIN}.',
            'address': str(addr),
            'type': 'A' if addr.version == 4 else 'AAAA'
        })

    remove_dns_entries(payload)


def cleanup_reverse_zone():
    result = call('smb.bindip_choices').values()
    ptr_table = {f'{ipaddress.ip_address(i).reverse_pointer}.': i for i in result}

    try:
        result = call('dnsclient.reverse_lookup', {'addresses': list(ptr_table.values())})
    except dns.resolver.NXDOMAIN:
        # No entry, nothing to do
        return

    payload = []
    for host in result:
        reverse_pointer = host["name"]
        assert reverse_pointer in ptr_table, str(ptr_table)
        addr = ipaddress.ip_address(ptr_table[reverse_pointer])
        payload.append({
            'command': 'DELETE',
            'name': host['target'],
            'address': str(addr),
            'type': 'A' if addr.version == 4 else 'AAAA'
        })

    remove_dns_entries(payload)


@pytest.fixture(scope="function")
def set_product_type(request):
    if ha:
        # HA product is already enterprise-licensed
        yield
    else:
        with product_type():
            yield


@pytest.fixture(scope="function")
def set_ad_nameserver(request):
    with override_nameservers() as ns:
        yield (request, ns)

@pytest.fixture(scope="module")
def enable_smb():
    call('service.update', 'cifs', {'enable': True})

    try:
        yield
    finally:
        call('service.update', 'cifs', {'enable': False})

def test_cleanup_nameserver(set_ad_nameserver, enable_smb):
    cred = call('kerberos.get_cred', {'dstype': 'DS_TYPE_ACTIVEDIRECTORY',
                                      'conf': {'bindname': ADUSERNAME,
                                               'bindpw': ADPASSWORD,
                                               'domainname': AD_DOMAIN
                                               }
                                      })

    call('kerberos.do_kinit', {'krb5_cred': cred,
                               'kinit-options': {'kdc_override': {'domain': AD_DOMAIN.upper(),
                                                                  'kdc': '10.238.238.2'
                                                                  },
                                                 }
                               })

    # Now that we have proper kinit as domain admin
    # we can nuke stale DNS entries from orbit.
    #
    cleanup_forward_zone()
    cleanup_reverse_zone()


def test_get_activedirectory_state(request):
    assert call('directoryservices.summary') is None


@pytest.mark.dependency(name="ad_works")
def test_enable_leave_activedirectory(request):
    if not ha:
        with pytest.raises(ValidationErrors):
            # At this point we are not enterprise licensed
            call("system.general.update", {"ds_auth": True})

    short_name = None

    with active_directory(dns_timeout=15) as ad:
        short_name = ad['domain_info']['pre-win2k_domain']

        # Make sure we can read our secrets.tdb file
        secrets_has_domain = call('directoryservices.secrets.has_domain', short_name)
        assert secrets_has_domain is True

        # Check that our database has backup of this info written to it.
        db_secrets = call('directoryservices.secrets.get_db_secrets')[f'{hostname.upper()}$']
        assert f'SECRETS/MACHINE_PASSWORD/{short_name}' in db_secrets

        # Last password change should be populated
        passwd_change = call('directoryservices.get_last_password_change')
        assert passwd_change['dbconfig'] is not None
        assert passwd_change['secrets'] is not None

        # We should be able tZZo change some parameters when joined to AD
        call('activedirectory.update', {'domainname': AD_DOMAIN, 'verbose_logging': True}, job=True)

        # Changing kerberos realm should raise ValidationError
        with pytest.raises(ClientValidationErrors) as ve:
            call('activedirectory.update', {'domainname': AD_DOMAIN, 'kerberos_realm': None}, job=True)

        assert ve.value.errors[0].errmsg.startswith('Kerberos realm may not be altered')

        # This should be caught by our catchall
        with pytest.raises(ClientValidationErrors) as ve:
            call('activedirectory.update', {'domainname': AD_DOMAIN, 'createcomputer': ''}, job=True)

        assert ve.value.errors[0].errmsg.startswith('Parameter may not be changed')

        # Verify that AD state is reported as healthy
        assert call('directoryservices.status')['status'] == 'HEALTHY'

        # Verify that idmapping is working
        pw = ad['user_obj']

        # Verify winbindd information
        assert pw['sid'] is not None, str(ad)
        assert not pw['sid'].startswith('S-1-22-1-'), str(ad)
        assert pw['local'] is False
        assert pw['source'] == 'WINBIND'

        result = call('dnsclient.forward_lookup', {'names': [f'{hostname}.{AD_DOMAIN}']})
        assert len(result) != 0

        addresses = [x['address'] for x in result]
        assert truenas_server.ip in addresses

        res = call('privilege.query', [['name', 'C=', AD_DOMAIN]], {'get': True})
        assert res['ds_groups'][0]['name'].endswith('domain admins')
        assert res['ds_groups'][0]['sid'].endswith('512')
        assert res['allowlist'][0] == {'method': '*', 'resource': '*'}

    assert call('directoryservices.status')['type'] is None

    secrets_has_domain = call('directoryservices.secrets.has_domain', short_name)
    assert secrets_has_domain is False

    with pytest.raises(KeyError):
        call('user.get_user_obj', {'username': AD_USER})

    assert call('directoryservices.summary') is None

    result = call('privilege.query', [['name', 'C=', AD_DOMAIN]])
    assert len(result) == 0, str(result)


def test_activedirectory_smb_ops(request):
    depends(request, ["ad_works"], scope="session")
    with active_directory(dns_timeout=15) as ad:
        short_name = ad['domain_info']['pre-win2k_domain']
        machine_password_key = f'SECRETS/MACHINE_PASSWORD/{short_name}'
        running_pwd = call('directoryservices.secrets.dump')[machine_password_key]
        db_pwd = call('directoryservices.secrets.get_db_secrets')[f'{hostname.upper()}$'][machine_password_key]

        # We've joined and left AD already. Verify secrets still getting backed up correctly.
        assert running_pwd == db_pwd

        with dataset(
            "ad_smb",
            {'share_type': 'SMB'},
            acl=[{
                'tag': 'GROUP',
                'id': ad['user_obj']['pw_uid'],
                'perms': {'BASIC': 'FULL_CONTROL'},
                'flags': {'BASIC': 'INHERIT'},
                'type': 'ALLOW'
            }]
        ) as ds:
            call('service.restart', 'cifs')

            with smb_share(f'/mnt/{ds}', {'name': SMB_NAME}):
                with smb_connection(
                    host=truenas_server.ip,
                    share=SMB_NAME,
                    username=ADUSERNAME,
                    domain='AD02',
                    password=ADPASSWORD
                ) as c:
                    fd = c.create_file('testfile.txt', 'w')
                    c.write(fd, b'foo')
                    val = c.read(fd, 0, 3)
                    c.close(fd, True)
                    assert val == b'foo'

                    c.mkdir('testdir')
                    fd = c.create_file('testdir/testfile2.txt', 'w')
                    c.write(fd, b'foo2')
                    val = c.read(fd, 0, 4)
                    c.close(fd, True)
                    assert val == b'foo2'

                    c.rmdir('testdir')

        with dataset(
            "ad_datasets",
            {'share_type': 'SMB'},
            acl=[{
                'tag': 'GROUP',
                'id': ad['user_obj']['pw_uid'],
                'perms': {'BASIC': 'FULL_CONTROL'},
                'flags': {'BASIC': 'INHERIT'},
                'type': 'ALLOW'
            }]
        ) as ds:
            with smb_share(f'/mnt/{ds}', {
                'name': 'DATASETS',
                'purpose': 'NO_PRESET',
                'auxsmbconf': 'zfs_core:zfs_auto_create = true',
                'path_suffix': '%D/%U'
            }):
                with smb_connection(
                    host=truenas_server.ip,
                    share='DATASETS',
                    username=ADUSERNAME,
                    domain='AD02',
                    password=ADPASSWORD
                ) as c:
                    fd = c.create_file('nested_test_file', "w")
                    c.write(fd, b'EXTERNAL_TEST')
                    c.close(fd)

            acl = call('filesystem.getacl', os.path.join(f'/mnt/{ds}', 'AD02', ADUSERNAME), True)
            assert acl['trivial'] is False, str(acl)

        with dataset(
            "ad_home",
            {'share_type': 'SMB'},
            acl=[{
                'tag': 'GROUP',
                'id': ad['user_obj']['pw_uid'],
                'perms': {'BASIC': 'FULL_CONTROL'},
                'flags': {'BASIC': 'INHERIT'},
                'type': 'ALLOW'
            }]
        ) as ds:

            with smb_share(f'/mnt/{ds}', {
                'name': 'TEST_HOME',
                'purpose': 'NO_PRESET',
                'home': True,
            }):
                # must refresh idmap cache to get new homedir from NSS
                # this means we may need a few seconds for winbindd
                # service to settle down on slow systems (like our CI VMs)
                sleep(10 if ha else 5)

                with smb_connection(
                    host=truenas_server.ip,
                    share='HOMES',
                    username=ADUSERNAME,
                    domain='AD02',
                    password=ADPASSWORD
                ) as c:
                    fd = c.create_file('homes_test_file', "w")
                    c.write(fd, b'EXTERNAL_TEST')
                    c.close(fd)

            file_local_path = os.path.join(f'/mnt/{ds}', 'AD02', ADUSERNAME, 'homes_test_file')
            acl = call('filesystem.getacl', file_local_path, True)
            assert acl['trivial'] is False, str(acl)


def test_account_privilege_authentication(request, set_product_type):
    depends(request, ["ad_works"], scope="session")

    with active_directory(dns_timeout=15):
        call("system.general.update", {"ds_auth": True})
        try:
            # RID 513 is constant for "Domain Users"
            domain_sid = call("idmap.domain_info", AD_DOMAIN.split(".")[0])['sid']
            with privilege({
                "name": "AD privilege",
                "local_groups": [],
                "ds_groups": [f"{domain_sid}-513"],
                "allowlist": [{"method": "CALL", "resource": "system.info"}],
                "web_shell": False,
            }):
                with client(auth=(f"limiteduser@{AD_DOMAIN}", ADPASSWORD)) as c:
                    methods = c.call("core.get_methods")
                    me = c.call("auth.me")

                    assert 'DIRECTORY_SERVICE' in me['account_attributes']
                    assert 'ACTIVE_DIRECTORY' in me['account_attributes']

                assert "system.info" in methods
                assert "pool.create" not in methods

                # ADUSERNAME is member of domain admins and will have
                # all privileges
                with client(auth=(f"{ADUSERNAME}@{AD_DOMAIN}", ADPASSWORD)) as c:
                    methods = c.call("core.get_methods")

                assert "pool.create" in methods

                # Alternative formatting for user name <DOMAIN>\<username>.
                # this should also work for auth
                with client(auth=(AD_USER, ADPASSWORD)) as c:
                    methods = c.call("core.get_methods")

                assert "pool.create" in methods

        finally:
            call("system.general.update", {"ds_auth": False})


def test_secrets_restore(request):
    depends(request, ["ad_works"], scope="session")
    reset_systemd_svcs('winbind smbd')

    with active_directory():
        assert call('directoryservices.status')['status'] == 'HEALTHY'
        ssh('rm /var/db/system/samba4/private/secrets.tdb')
        call('service.restart', 'idmap')

        with pytest.raises(KeyError):
            call('user.get_user_obj', {'username': AD_USER})

        call('directoryservices.secrets.restore')
        call('service.restart', 'idmap')
        call('user.get_user_obj', {'username': AD_USER})

        # break it again and restore via the alert source
        reset_systemd_svcs('winbind smbd')
        ssh('rm /var/db/system/samba4/private/secrets.tdb')
        call('service.restart', 'idmap')

        with pytest.raises(KeyError):
            call('user.get_user_obj', {'username': AD_USER})

        # Our periodic health check alert should be able to
        # recover from this
        alerts = call('alert.run_source', 'ActiveDirectoryDomainBind')
        assert alerts == [], str(alerts)
        call('user.get_user_obj', {'username': AD_USER})


def test_keytab_restore(request):
    depends(request, ["ad_works"], scope="session")
    reset_systemd_svcs('winbind smbd')

    with active_directory():
        assert call('directoryservices.status')['status'] == 'HEALTHY'

        kt_id = call('kerberos.keytab.query', [['name', '=', 'AD_MACHINE_ACCOUNT']], {'get': True})['id']

        # delete our keytab from datastore
        call('datastore.delete', 'directoryservice.kerberoskeytab', kt_id)

        # This should be recoverable when running our AD alert source
        alerts = call('alert.run_source', 'ActiveDirectoryDomainBind')
        assert alerts == [], str(alerts)

        # Our periodic health check alert should be able to
        # recover from this
        call('kerberos.keytab.query', [['name', '=', 'AD_MACHINE_ACCOUNT']], {'get': True})
