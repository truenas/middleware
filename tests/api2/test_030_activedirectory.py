#!/usr/bin/env python3

import os
import json
import sys
import pytest
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from assets.REST.directory_services import active_directory
from assets.REST.pool import dataset
from auto_config import pool_name, ip, user, password, ha
from functions import GET, POST, PUT, DELETE, SSH_TEST, cmd_test, wait_on_job
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


@pytest.mark.dependency(name="ad_01")
def test_01_get_nameserver1(request):
    global nameserver1
    results = GET("/network/configuration/")
    assert results.status_code == 200, results.text
    nameserver1 = results.json()['nameserver1']


@pytest.mark.dependency(name="ad_02")
def test_02_set_nameserver_for_ad(request):
    depends(request, ["ad_01"], scope="session")
    global payload
    payload = {
        "nameserver1": ADNameServer,
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_03_get_activedirectory_data(request):
    depends(request, ["ad_01", "ad_02"], scope="session")
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', list(ad_data_type.keys()))
def test_04_verify_activedirectory_data_type_of_the_object_value_of_(request, data):
    depends(request, ["ad_02"], scope="session")
    assert isinstance(results.json()[data], ad_data_type[data]), results.text


def test_05_get_activedirectory_state(request):
    depends(request, ["ad_01", "ad_02"], scope="session")
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_06_get_activedirectory_started_before_starting_activedirectory(request):
    depends(request, ["ad_01", "ad_02"], scope="session")
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
