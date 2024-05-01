import ipaddress
import os
import sys
from time import sleep

import pytest
from pytest_dependency import depends

apifolder = os.getcwd()
sys.path.append(apifolder)
from assets.REST.directory_services import active_directory, override_nameservers
from auto_config import pool_name, ip, user, password, ha
from functions import GET, POST, PUT, DELETE, SSH_TEST, cmd_test, make_ws_request, wait_on_job
from protocols import smb_connection, smb_share

from middlewared.service_exception import ValidationErrors, ValidationError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import call, client
from middlewared.test.integration.assets.product import product_type

if ha and "hostname_virtual" in os.environ:
    hostname = os.environ["hostname_virtual"]
else:
    from auto_config import hostname

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer, AD_COMPUTER_OU
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


@pytest.fixture(scope="module")
def set_ad_nameserver(request):
    with override_nameservers(ADNameServer) as ns:
        yield (request, ns)


def test_01_set_nameserver_for_ad(set_ad_nameserver):
    assert set_ad_nameserver[1]['nameserver1'] == ADNameServer


def test_02_cleanup_nameserver(request):
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
    global domain_users_id

    if not ha:
        with pytest.raises(ValidationErrors):
            # At this point we are not enterprise licensed
            call("system.general.update", {"ds_auth": True})

    with active_directory(AD_DOMAIN, ADUSERNAME, ADPASSWORD,
        netbiosname=hostname,
        createcomputer=AD_COMPUTER_OU,
        dns_timeout=15
    ) as ad:
        # We should be able to change some parameters when joined to AD
        call('activedirectory.update', {'domainname': AD_DOMAIN, 'verbose_logging': True})

        # Changing kerberos realm should raise ValidationError
        with pytest.raises(ValidationErrors) as ve:
            call('activedirectory.update', {'domainname': AD_DOMAIN, 'kerberos_realm': None})

        assert ve.value.errors[0].errmsg.startswith('Kerberos realm may not be altered')

        # This should be caught by our catchall
        with pytest.raises(ValidationError) as ve:
            call('activedirectory.update', {'domainname': AD_DOMAIN, 'createcomputer': ''})

        assert ve.value.errmsg.startswith('Parameter may not be changed')

        # Verify that we're not leaking passwords into middleware log
        cmd = f"""grep -R "{ADPASSWORD}" /var/log/middlewared.log"""
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is False, str(results['output'])

        # Verify that AD state is reported as healthy
        results = GET('/activedirectory/get_state/')
        assert results.status_code == 200, results.text
        assert results.json() == 'HEALTHY', results.text

        # Verify that `started` endpoint works correctly
        results = GET('/activedirectory/started/')
        assert results.status_code == 200, results.text
        assert results.json() is True, results.text


        # Verify that idmapping is working
        results = POST("/user/get_user_obj/", {'username': AD_USER, 'sid_info': True})
        assert results.status_code == 200, results.text
        assert results.json()['pw_name'] == AD_USER, results.text
        pw = results.json()
        domain_users_id = pw['pw_gid']

        # Verify winbindd information
        assert pw['sid_info'] is not None, results.text
        assert not pw['sid_info']['sid'].startswith('S-1-22-1-'), results.text
        assert pw['sid_info']['domain_information']['domain'] != 'LOCAL', results.text
        assert pw['sid_info']['domain_information']['domain_sid'] is not None, results.text
        assert pw['sid_info']['domain_information']['online'], results.text
        assert pw['sid_info']['domain_information']['activedirectory'], results.text

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

        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'privilege.query',
            'params': [[['name', 'C=', AD_DOMAIN]]]
        })
        error = res.get('error')
        assert error is None, str(error)
        assert len(res['result']) == 1, str(res['result'])

        assert len(res['result'][0]['ds_groups']) == 1, str(res['result'])
        assert res['result'][0]['ds_groups'][0]['name'].endswith('domain admins')
        assert res['result'][0]['ds_groups'][0]['sid'].endswith('512')
        assert res['result'][0]['allowlist'][0] == {'method': '*', 'resource': '*'}

        assert call('directoryservices.secrets_has_domain', 'AD02')

    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text

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

    assert call('directoryservices.secrets_has_domain', 'AD02') is False


def test_08_activedirectory_smb_ops(request):
    depends(request, ["ad_works"], scope="session")
    with active_directory(AD_DOMAIN, ADUSERNAME, ADPASSWORD,
        netbiosname=hostname,
        createcomputer=AD_COMPUTER_OU,
        dns_timeout=15
    ) as ad:
        with dataset(
            "ad_smb",
            {'share_type': 'SMB'},
            acl=[{
                'tag': 'GROUP',
                'id': domain_users_id,
                'perms': {'BASIC': 'FULL_CONTROL'},
                'flags': {'BASIC': 'INHERIT'},
                'type': 'ALLOW'
            }]
        ) as ds:
            results = POST("/service/restart/", {"service": "cifs"})
            assert results.status_code == 200, results.text

            with smb_share(f'/mnt/{ds}', {'name': SMB_NAME}) as share:
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
                'id': domain_users_id,
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
                'id': domain_users_id,
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

    with active_directory(AD_DOMAIN, ADUSERNAME, ADPASSWORD,
        netbiosname=hostname,
        createcomputer=AD_COMPUTER_OU,
        dns_timeout=15
    ):
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
