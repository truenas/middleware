import pytest

from config import CLUSTER_INFO, CLUSTER_IPS, CLUSTER_LDAP, PUBLIC_IPS
from utils import make_request, make_ws_request, ssh_test, wait_on_job
from exceptions import JobTimeOut
from pytest_dependency import depends

SHARE_FUSE_PATH = f'CLUSTER:{CLUSTER_INFO["GLUSTER_VOLUME"]}/ds_smb_share_02'


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name='DS_LDAP_NETWORK_CONFIGURED')
def test_002_validate_network_configuration(ip, request):
    url = f'http://{ip}/api/v2.0/network/configuration/'
    res = make_request('get', url)
    assert res.status_code == 200, res.text

    data = res.json()
    assert data['nameserver1'] == CLUSTER_INFO['DNS1']
    assert data['ipv4gateway'] == CLUSTER_INFO['DEFGW']


@pytest.mark.dependency(name="BOUND_LDAP")
def test_003_bind_ldap(request):
    depends(request, ['DS_LDAP_NETWORK_CONFIGURED'])

    payload = {
        "hostname": [CLUSTER_LDAP['HOSTNAME']],
        "basedn": CLUSTER_LDAP['BASEDN'],
        "binddn": CLUSTER_LDAP['BINDDN'],
        "bindpw": CLUSTER_LDAP['BINDPW'],
        "ssl": "ON",
        "enable": True
    }
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/ldap/'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json()['job_id'], CLUSTER_IPS[0], 300)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    for ip in CLUSTER_IPS:
        payload = {
            'msg': 'method',
            'method': 'ldap.started',
        }
        res = make_ws_request(ip, payload)
        assert res.get('error') is None, res

        url = f'http://{ip}/api/v2.0/ldap/get_state'
        res = make_request('get', url)
        assert res.status_code == 200, f'ip: {ip}, res: {res.text}'
        assert res.json() == 'HEALTHY'


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name="LDAP_ACCOUNTS_CONFIGURED")
def test_004_verify_ldap_accounts_present(ip, request):
    depends(request, ['BOUND_LDAP'])

    passwd = ssh_test(ip, "getent passwd")

    payload = {"username": CLUSTER_LDAP["TEST_USERNAME"]}
    url = f'http://{ip}/api/v2.0/user/get_user_obj/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, passwd['output']

    payload = {"groupname": CLUSTER_LDAP["TEST_GROUPNAME"]}
    url = f'http://{ip}/api/v2.0/group/get_group_obj/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_005_validate_cached_ldap_accounts(ip, request):
    depends(request, ['LDAP_ACCOUNTS_CONFIGURED'])

    payload = {
        'query-filters': [["method", "=", "ldap.fill_cache"]],
        'query-options': {'order_by': ['-id']},
    }
    url = f'http://{ip}/api/v2.0/core/get_jobs'
    res = make_request('get', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json()[0]['id'], ip, 300)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    payload = {
        'query-filters': [["local", "=", False]],
        'query-options': {'extra': {"additional_information": ['DS']}},
    }
    url = f'http://{ip}/api/v2.0/user'
    res = make_request('get', url, data=payload)
    assert res.status_code == 200, res.text
    assert len(res.json()) != 0, 'No cached users'

    url = f'http://{ip}/api/v2.0/group'
    res = make_request('get', url, data=payload)
    assert res.status_code == 200, res.text
    assert len(res.json()) != 0, 'No cached groups'


def test_050_unbind_ldap(request):
    depends(request, ['BOUND_LDAP'])

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/ldap'
    payload = {
        "has_samba_schema": False,
        "enable": False,
    }
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json()['job_id'], CLUSTER_IPS[0], 300)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    for ip in CLUSTER_IPS:
        url = f'http://{ip}/api/v2.0/ldap/get_state'
        res = make_request('get', url)
        assert res.status_code == 200, f'ip: {ip}, res: {res.text}'
        assert res.json() == 'DISABLED'

        payload = {
            'msg': 'method',
            'method': 'ldap.started',
        }
        res = make_ws_request(ip, payload)
        assert res.get('error') is None, res
