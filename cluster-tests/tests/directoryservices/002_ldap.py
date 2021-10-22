import pytest

from config import CLUSTER_INFO, CLUSTER_IPS, CLUSTER_LDAP
from utils import make_request, make_ws_request, ssh_test, wait_on_job
from exceptions import JobTimeOut
from pytest_dependency import depends
from helpers import smb_connection
from samba import ntstatus, NTSTATUSError

SHARE_FUSE_PATH = f'CLUSTER:{CLUSTER_INFO["GLUSTER_VOLUME"]}/ds_smb_share_02'


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name="CTDB_IS_HEALTHY")
def test_001_ctdb_is_healthy(ip):
    url = f'http://{ip}/api/v2.0/ctdb/general/healthy'
    res = make_request('get', url)
    assert res.status_code == 200, res.text
    assert res.json() is True, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name="CTDB_HAS_PUBLIC_IPS")
def test_002_ctdb_public_ip_check(ip, request):
    depends(request, ['CTDB_IS_HEALTHY'])

    payload = {'all_nodes': False}
    url = f'http://{ip}/api/v2.0/ctdb/general/status/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    this_node = res.json()[0]['pnn']

    payload = {
        'query-filters': [["id", "=", this_node]],
    }
    url = f'http://{ip}/api/v2.0/ctdb/public/ips'
    res = make_request('get', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        data = set(res.json()[0]['configured_ips'].keys())
    except (KeyError, IndexError):
        data = set()

    to_add = set(CLUSTER_INFO['PUBLIC_IPS']) - data

    assert data or to_add, data
    for entry in to_add:
        payload = {
            "pnn": this_node,
            "ip": entry,
            "netmask": CLUSTER_INFO['NETMASK'],
            "interface": CLUSTER_INFO['INTERFACE'],
        }
        res = make_request('post', url, data=payload)
        assert res.status_code == 200, res.text
        try:
            status = wait_on_job(res.json(), ip, 5)
        except JobTimeOut:
            assert False, JobTimeOut
        else:
            assert status['state'] == 'SUCCESS', status

        assert status['result']


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_003_validate_smb_bind_ips(ip, request):
    depends(request, ['CTDB_HAS_PUBLIC_IPS'])

    url = f'http://{ip}/api/v2.0/smb/bindip_choices'
    res = make_request('get', url)
    assert res.status_code == 200, res.text

    smb_ip_set = set(res.json().values())
    cluster_ip_set = set(CLUSTER_INFO['PUBLIC_IPS'])
    assert smb_ip_set == cluster_ip_set, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name="DS_LDAP_NETWORK_CONFIGURED")
def test_004_validate_network_configuration(ip, request):
    depends(request, ['CTDB_HAS_PUBLIC_IPS'])

    url = f'http://{ip}/api/v2.0/network/configuration/'
    res = make_request('get', url)
    assert res.status_code == 200, res.text

    data = res.json()
    assert data['nameserver1'] == CLUSTER_INFO['DNS1']
    assert data['ipv4gateway'] == CLUSTER_INFO['DEFGW']


@pytest.mark.dependency(name="BOUND_LDAP")
def test_005_bind_ldap(request):
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
def test_006_verify_ldap_accounts_present(ip, request):
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
def test_007_validate_cached_ldap_accounts(ip, request):
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


@pytest.mark.dependency(name="DS_LDAP_SMB_SHARE_CREATED")
def test_010_create_clustered_smb_share(request):
    depends(request, ['BOUND_LDAP'])
    global ds_smb_share_id
    global ds_wrk

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/mkdir/'
    res = make_request('post', url, data=SHARE_FUSE_PATH)
    assert res.status_code == 200, res.text

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/user/get_user_obj/'
    payload = {"username": CLUSTER_LDAP["TEST_USERNAME"]}
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    user_obj = res.json()

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/chown/'
    payload = {"path": SHARE_FUSE_PATH, "uid": user_obj["pw_uid"]}
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json(), CLUSTER_IPS[0], 300)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/'
    payload = {
        "comment": "LDAP clustered SMB share",
        "path": '/ds_smb_share_02',
        "name": "DS_CL_SMB2",
        "purpose": "NO_PRESET",
        "shadowcopy": False,
        "cluster_volname": CLUSTER_INFO["GLUSTER_VOLUME"]
    }

    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    ds_smb_share_id = res.json()['id']

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/smb'
    res = make_request('get', url)
    assert res.status_code == 200, res.text
    ds_wrk = res.json()['workgroup']


@pytest.mark.parametrize('ip', CLUSTER_INFO['PUBLIC_IPS'])
def test_011_auth_known_failure_nosmb(ip, request):
    """
    Samba schema is disable. SMB auth should fail
    with STATUS_LOGON_FAILURE.
    """
    depends(request, ['DS_LDAP_SMB_SHARE_CREATED'])

    with pytest.raises(NTSTATUSError) as e:
        with smb_connection(
            host=ip,
            share="DS_CL_SMB2",
            username=CLUSTER_LDAP['TEST_USERNAME'],
            domain=ds_wrk,
            password=CLUSTER_LDAP['TEST_PASSWORD'],
            smb1=False
        ) as tcon:
            fd = tcon.create_file("testfile", "w")
            tcon.close(fd, True)

    assert e.value.args[0] == ntstatus.NT_STATUS_LOGON_FAILURE, e.value.args[1]


@pytest.mark.dependency(name="BOUND_LDAP_SMB")
def test_012_bind_ldap(request):
    depends(request, ['DS_LDAP_SMB_SHARE_CREATED', 'BOUND_LDAP'])

    payload = {
        "has_samba_schema": True,
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


@pytest.mark.dependency(name="DS_LDAP_SMB_SHARE_IS_WRITABLE")
@pytest.mark.parametrize('ip', CLUSTER_INFO['PUBLIC_IPS'])
def test_014_share_is_writable_via_public_ips(ip, request):
    """
    This test verifies that the SMB share is writable once
    we enable a samba schema.
    """
    depends(request, ['DS_LDAP_SMB_SHARE_CREATED', 'BOUND_LDAP_SMB'])

    with smb_connection(
        host=ip,
        share="DS_CL_SMB2",
        username=CLUSTER_LDAP['TEST_USERNAME'],
        domain=ds_wrk,
        password=CLUSTER_LDAP['TEST_PASSWORD'],
        smb1=False
    ) as tcon:
        fd = tcon.create_file("testfile", "w")
        tcon.close(fd, True)


def test_015_xattrs_writable_via_smb(request):
    depends(request, ['DS_LDAP_SMB_SHARE_IS_WRITABLE'])

    with smb_connection(
        host=CLUSTER_INFO['PUBLIC_IPS'][0],
        share="DS_CL_SMB2",
        username=CLUSTER_LDAP['TEST_USERNAME'],
        domain=ds_wrk,
        password=CLUSTER_LDAP['TEST_PASSWORD'],
        smb1=False
    ) as tcon:
        fd = tcon.create_file("streamstestfile:smb2_stream", "w")
        tcon.write(fd, b'test1', 0)
        tcon.close(fd)

        fd2 = tcon.create_file("streamstestfile:smb2_stream", "w")
        contents = tcon.read(fd2, 0, 5)
        tcon.close(fd2)

    assert(contents.decode() == "test1")


def test_048_delete_clustered_smb_share(request):
    depends(request, ['DS_LDAP_SMB_SHARE_CREATED'])

    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/sharing/smb/id/{ds_smb_share_id}'
    res = make_request('delete', url)
    assert res.status_code == 200, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_049_verify_clustered_share_removed(ip, request):
    depends(request, ['DS_LDAP_SMB_SHARE_CREATED'])

    url = f'http://{ip}/api/v2.0/sharing/smb?id={ds_smb_share_id}'
    res = make_request('get', url)
    assert res.status_code == 200, res.text
    assert res.json() == [], res.text

    cmd = f'rm -rf /cluster/{CLUSTER_INFO["GLUSTER_VOLUME"]}/ds_smb_share_02'
    res = ssh_test(CLUSTER_IPS[0], cmd)
    assert res['result'], res['stderr']


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
