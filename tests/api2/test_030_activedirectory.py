#!/usr/bin/env python3

import os
import ipaddress
import json
import sys
import pytest
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from assets.REST.directory_services import active_directory, override_nameservers
from assets.REST.pool import dataset
from auto_config import pool_name, ip, user, password, ha
from functions import GET, POST, PUT, DELETE, SSH_TEST, cmd_test, make_ws_request, wait_on_job
from protocols import smb_connection, smb_share

if ha and "hostname_virtual" in os.environ:
    hostname = os.environ["hostname_virtual"]
else:
    from auto_config import hostname

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer
    AD_USER = fr"AD02\{ADUSERNAME.lower()}"
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)
else:
    from auto_config import dev_test
    # comment pytestmark for development testing with --dev-test
    pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


ad_data_type = {
    'id': int,
    'domainname': str,
    'bindname': str,
    'bindpw': str,
    'verbose_logging': bool,
    'allow_trusted_doms': bool,
    'use_default_domain': bool,
    'allow_dns_updates': bool,
    'disable_freenas_cache': bool,
    'site': type(None),
    'kerberos_realm': type(None),
    'kerberos_principal': str,
    'createcomputer': str,
    'timeout': int,
    'dns_timeout': int,
    'nss_info': type(None),
    'enable': bool,
    'netbiosname': str,
    'netbiosalias': list
}

ad_object_list = [
    "bindname",
    "domainname",
    "netbiosname",
    "enable"
]

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
            {'hostname': f'{hostname}.{AD_DOMAIN}.', 'clustered': False, 'bindip': []},
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


@pytest.mark.parametrize('data', list(ad_data_type.keys()))
def test_04_verify_activedirectory_data_type_of_the_object_value_of_(request, data):
    assert isinstance(results.json()[data], ad_data_type[data]), results.text


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
    with active_directory(AD_DOMAIN, ADUSERNAME, ADPASSWORD,
        netbiosname=hostname,
        dns_timeout=15
    ) as ad:
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
        results = POST("/user/get_user_obj/", {'username': AD_USER})
        assert results.status_code == 200, results.text
        assert results.json()['pw_name'] == AD_USER, results.text
        domain_users_id = results.json()['pw_gid']

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

    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text

    results = POST("/user/get_user_obj/", {'username': AD_USER})
    assert results.status_code != 200, results.text

    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


def test_08_activedirectory_smb_ops(request):
    depends(request, ["ad_works"], scope="session")
    with active_directory(AD_DOMAIN, ADUSERNAME, ADPASSWORD,
        netbiosname=hostname,
        dns_timeout=15
    ) as ad:
        with dataset(
            pool_name,
            "ad_smb",
            options={'share_type': 'SMB'},
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

            with smb_share(ds['mountpoint'], {'name': SMB_NAME}) as share:
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
            pool_name,
            "ad_datasets",
            options={'share_type': 'SMB'},
            acl=[{
                'tag': 'GROUP',
                'id': domain_users_id,
                'perms': {'BASIC': 'FULL_CONTROL'},
                'flags': {'BASIC': 'INHERIT'},
                'type': 'ALLOW'
            }]
        ) as ds:
            with smb_share(ds['mountpoint'], {
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
                'path': os.path.join(ds['mountpoint'], 'AD02', ADUSERNAME),
                'simplified': True
            })

            assert results.status_code == 200, results.text
            acl = results.json()
            assert acl['trivial'] is False, str(acl)
