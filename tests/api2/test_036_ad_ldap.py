#!/usr/bin/env python3

import pytest
import sys
import os
import json
apifolder = os.getcwd()
sys.path.append(apifolder)

from assets.REST.directory_services import active_directory, ldap, override_nameservers
from auto_config import ip, hostname, password, user
from contextlib import contextmanager
from functions import GET, POST, PUT, make_ws_request, wait_on_job
from pytest_dependency import depends

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)
else:
    from auto_config import dev_test
    # comment pytestmark for development testing with --dev-test
    pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

@pytest.fixture(scope="module")
def kerberos_config(request):
    payload = {"v4_krb": True}
    results = PUT("/nfs/", payload)
    assert results.status_code == 200, results.text
    try:
        yield (request, results.json())
    finally:
        payload = {"v4_krb": False}
        results = PUT("/nfs/", payload)
        assert results.status_code == 200, results.text


@pytest.fixture(scope="module")
def do_ad_connection(request):
    with active_directory(
        AD_DOMAIN,
        ADUSERNAME,
        ADPASSWORD,
        netbiosname=hostname,
    ) as ad:
        yield (request, ad)


@contextmanager
def stop_activedirectory(request):
    results = PUT("/activedirectory/", {"enable": False})
    assert results.status_code == 200, results.text
    job_id = results.json()['job_id']
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    try:
        yield results.json()
    finally:
        results = PUT("/activedirectory/", {"enable": True})
        assert results.status_code == 200, results.text
        job_id = results.json()['job_id']
        job_status = wait_on_job(job_id, 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.fixture(scope="module")
def do_ldap_connection(request):

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.keytab.kerberos_principal_choices',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    kerberos_principal = res['result'][0]

    results = GET("/kerberos/realm/")
    assert results.status_code == 200, results.text

    realm_id = results.json()[0]['id']

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos._klist_test',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is True

    results = POST("/activedirectory/domain_info/", AD_DOMAIN)
    assert results.status_code == 200, results.text
    domain_info = results.json()

    with stop_activedirectory(request) as ad:
        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'kerberos.get_cred',
            'params': [{
                'dstype': 'DS_TYPE_LDAP',
                'conf': {
                    'kerberos_realm': realm_id,
                    'kerberos_principal': kerberos_principal,
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

        with ldap(
            domain_info['Bind Path'],
            '', '', f'{domain_info["LDAP server name"].upper()}.',
            has_samba_schema=False,
            ssl="OFF",
            kerberos_realm=realm_id,
            kerberos_principal=kerberos_principal,
            validate_certificates=False,
            enable=True
        ) as ldap_conn:
            yield (request, ldap_conn)


@pytest.fixture(scope="module")
def set_ad_nameserver(request):
    with override_nameservers(ADNameServer) as ns:
        yield (request, ns)


def test_01_set_nameserver_for_ad(set_ad_nameserver):
    assert set_ad_nameserver[1]['nameserver1'] == ADNameServer


@pytest.mark.dependency(name="AD_CONFIGURED")
def test_02_enabling_activedirectory(do_ad_connection):
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text

    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


def test_03_kerberos_nfs4_spn_add(kerberos_config):
    depends(kerberos_config[0], ["AD_CONFIGURED"], scope="session")
    assert kerberos_config[1]['v4_krb_enabled']

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.keytab.has_nfs_principal',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is False

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'nfs.add_principal',
        'params': [{
            'username': ADUSERNAME,
            'password': ADPASSWORD
        }],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is True

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.keytab.has_nfs_principal',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is True


@pytest.mark.dependency(name="SET_UP_AD_VIA_LDAP")
def test_04_setup_and_enabling_ldap(do_ldap_connection):
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.stop',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.start',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos._klist_test',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is True

    # Verify that our NFS kerberos principal is
    # still present
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.keytab.has_nfs_principal',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is True


def test_05_verify_ldap_users(request):
    depends(request, ["SET_UP_AD_VIA_LDAP"], scope="session")

    results = GET('/user', payload={
        'query-filters': [['local', '=', False]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text

    results = GET('/group', payload={
        'query-filters': [['local', '=', False]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text
