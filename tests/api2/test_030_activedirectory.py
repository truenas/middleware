import ipaddress
import errno
import os
import sys
from time import sleep

import pytest
from pytest_dependency import depends

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import ip, ha
from functions import GET, POST, make_ws_request
from protocols import smb_connection, smb_share

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.client.client import ValidationErrors as ClientValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.assets.directory_service import active_directory, override_nameservers
from middlewared.test.integration.utils import call, ssh, client
from middlewared.test.integration.assets.product import product_type

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
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'dns.nsupdate',
        'params': [{'ops': payload}]
    })
    error = res.get('error')
    assert error is None, str(error)


def cleanup_forward_zone():
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'dnsclient.forward_lookup',
        'params': [{'names': [f'{hostname}.{AD_DOMAIN}']}]
    })
    error = res.get('error')

    if error and error['trace']['class'] == 'NXDOMAIN':
        # No entry, nothing to do
        return

    assert error is None, str(error)
    ips_to_remove = [rdata['address'] for rdata in res['result']]

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
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'activedirectory.ipaddresses_to_register',
        'params': [
            {'hostname': f'{hostname}.{AD_DOMAIN}.', 'bindip': []},
            False
        ],
    })
    error = res.get('error')
    assert error is None, str(error)
    ptr_table = {f'{ipaddress.ip_address(i).reverse_pointer}.': i for i in res['result']}

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'dnsclient.reverse_lookup',
        'params': [{'addresses': list(ptr_table.values())}],
    })
    error = res.get('error')
    if error and error['trace']['class'] == 'NXDOMAIN':
        # No entry, nothing to do
        return

    assert error is None, str(error)

    payload = []
    for host in res['result']:
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


def test_02_cleanup_nameserver(set_ad_nameserver):
    results = POST("/activedirectory/domain_info/", AD_DOMAIN)
    assert results.status_code == 200, results.text
    domain_info = results.json()

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.get_cred',
        'params': [{
            'dstype': 'DS_TYPE_ACTIVEDIRECTORY',
            'conf': {
                'bindname': ADUSERNAME,
                'bindpw': ADPASSWORD,
                'domainname': AD_DOMAIN,
            }
        }],
    })
    error = res.get('error')
    assert error is None, str(error)
    cred = res['result']

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.do_kinit',
        'params': [{
            'krb5_cred': cred,
            'kinit-options': {
                'kdc_override': {
                    'domain': AD_DOMAIN.upper(),
                    'kdc': domain_info['KDC server']
                },
            }
        }],
    })
    error = res.get('error')
    assert error is None, str(error)

    # Now that we have proper kinit as domain admin
    # we can nuke stale DNS entries from orbit.
    #
    cleanup_forward_zone()
    cleanup_reverse_zone()


def test_03_get_activedirectory_data(request):
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


def test_05_get_activedirectory_state(request):
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_06_get_activedirectory_started_before_starting_activedirectory(request):
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


@pytest.mark.dependency(name="ad_works")
def test_07_enable_leave_activedirectory(request):
    if not ha:
        with pytest.raises(ValidationErrors):
            # At this point we are not enterprise licensed
            call("system.general.update", {"ds_auth": True})

    short_name = None

    with active_directory(dns_timeout=15) as ad:
        short_name = ad['dc_info']['Pre-Win2k Domain']

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
        assert call('activedirectory.get_state') == 'HEALTHY'

        # Verify that `started` endpoint works correctly
        assert call('activedirectory.started') is True

        # Verify that idmapping is working
        pw = ad['user_obj']

        # Verify winbindd information
        assert pw['sid_info'] is not None, str(ad)
        assert not pw['sid_info']['sid'].startswith('S-1-22-1-'), str(ad)
        assert pw['sid_info']['domain_information']['domain'] != 'LOCAL', str(ad)
        assert pw['sid_info']['domain_information']['domain_sid'] is not None, str(ad)
        assert pw['sid_info']['domain_information']['online'], str(ad)
        assert pw['sid_info']['domain_information']['activedirectory'], str(ad)

        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'dnsclient.forward_lookup',
            'params': [{'names': [f'{hostname}.{AD_DOMAIN}']}],
        })
        error = res.get('error')
        assert error is None, str(error)
        assert len(res['result']) != 0

        addresses = [x['address'] for x in res['result']]
        assert ip in addresses

        res = call('privilege.query', [['name', 'C=', AD_DOMAIN]], {'get': True})
        assert res['ds_groups'][0]['name'].endswith('domain admins')
        assert res['ds_groups'][0]['sid'].endswith('512')
        assert res['allowlist'][0] == {'method': '*', 'resource': '*'}

    assert call('activedirectory.get_state') == 'DISABLED'

    secrets_has_domain = call('directoryservices.secrets.has_domain', short_name)
    assert secrets_has_domain is False

    results = POST("/user/get_user_obj/", {'username': AD_USER})
    assert results.status_code != 200, results.text

    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'privilege.query',
        'params': [[['name', 'C=', AD_DOMAIN]]]
    })
    error = res.get('error')
    assert error is None, str(error)
    assert len(res['result']) == 0, str(res['result'])


def test_08_activedirectory_smb_ops(request):
    depends(request, ["ad_works"], scope="session")
    with active_directory(dns_timeout=15) as ad:
        short_name = ad['dc_info']['Pre-Win2k Domain']
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
            results = POST("/service/restart/", {"service": "cifs"})
            assert results.status_code == 200, results.text

            with smb_share(f'/mnt/{ds}', {'name': SMB_NAME}):
                with smb_connection(
                    host=ip,
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
                    host=ip,
                    share='DATASETS',
                    username=ADUSERNAME,
                    domain='AD02',
                    password=ADPASSWORD
                ) as c:
                    fd = c.create_file('nested_test_file', "w")
                    c.write(fd, b'EXTERNAL_TEST')
                    c.close(fd)

            results = POST('/filesystem/getacl/', {
                'path': os.path.join(f'/mnt/{ds}', 'AD02', ADUSERNAME),
                'simplified': True
            })

            assert results.status_code == 200, results.text
            acl = results.json()
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
            results = POST("/service/restart/", {"service": "cifs"})
            assert results.status_code == 200, results.text

            with smb_share(f'/mnt/{ds}', {
                'name': 'TEST_HOME',
                'purpose': 'NO_PRESET',
                'home': True,
            }):
                # must refresh idmap cache to get new homedir from NSS
                # this means we may need a few seconds for winbindd
                # service to settle down on slow systems (like our CI VMs)
                sleep(5)

                with smb_connection(
                    host=ip,
                    share='HOMES',
                    username=ADUSERNAME,
                    domain='AD02',
                    password=ADPASSWORD
                ) as c:
                    fd = c.create_file('homes_test_file', "w")
                    c.write(fd, b'EXTERNAL_TEST')
                    c.close(fd)

            file_local_path = os.path.join(f'/mnt/{ds}', 'AD02', ADUSERNAME, 'homes_test_file')
            results = POST('/filesystem/getacl/', {
                'path': file_local_path,
                'simplified': True
            })

            assert results.status_code == 200, results.text
            acl = results.json()
            assert acl['trivial'] is False, str(acl)


def test_10_account_privilege_authentication(request, set_product_type):
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


def test_11_secrets_restore(request):
    depends(request, ["ad_works"], scope="session")

    with active_directory():
        assert call('activedirectory.started') is True
        ssh('rm /var/db/system/samba4/private/secrets.tdb')
        call('service.restart', 'idmap')

        with pytest.raises(CallError) as ce:
            call('activedirectory.started')

        # WBC_ERR_WINBIND_NOT_AVAILABLE gets converted to ENOTCONN
        assert 'WBC_ERR_WINBIND_NOT_AVAILABLE' in ce.value.errmsg

        call('directoryservices.secrets.restore')
        call('service.restart', 'idmap')
        call('activedirectory.started')
