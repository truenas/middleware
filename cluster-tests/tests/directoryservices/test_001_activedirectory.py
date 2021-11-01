import pytest

from config import CLUSTER_INFO, CLUSTER_IPS, CLUSTER_ADS, PUBLIC_IPS
from utils import make_request, make_ws_request, ssh_test, wait_on_job
from exceptions import JobTimeOut
from pytest_dependency import depends
from helpers import smb_connection

SHARE_FUSE_PATH = f'CLUSTER:{CLUSTER_INFO["GLUSTER_VOLUME"]}/ds_smb_share_01'


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name='VALID_SMB_BIND_IPS')
def test_001_validate_smb_bind_ips(ip, request):
    url = f'http://{ip}/api/v2.0/smb/bindip_choices'
    res = make_request('get', url)
    assert res.status_code == 200, res.text

    smb_ip_set = set(res.json().values())
    cluster_ip_set = set(PUBLIC_IPS)
    assert smb_ip_set == cluster_ip_set, smb_ip_set


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name="DS_NETWORK_CONFIGURED")
def test_002_validate_network_configuration(ip, request):
    depends(request, ['VALID_SMB_BIND_IPS'])

    url = f'http://{ip}/api/v2.0/network/configuration/'
    res = make_request('get', url)
    assert res.status_code == 200, res.text

    data = res.json()
    assert data['nameserver1'] == CLUSTER_INFO['DNS1']
    assert data['ipv4gateway'] == CLUSTER_INFO['DEFGW']

    payload = CLUSTER_ADS['DOMAIN']
    url = f'http://{ip}/api/v2.0/activedirectory/domain_info/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    domain_info = res.json()
    assert abs(domain_info['Server time offset']) < 180


@pytest.mark.dependency(name="JOINED_AD")
def test_003_join_activedirectory(request):
    depends(request, ['DS_NETWORK_CONFIGURED'])

    payload = {
        "domainname": CLUSTER_ADS['DOMAIN'],
        "bindname": CLUSTER_ADS['USERNAME'],
        "bindpw": CLUSTER_ADS['PASSWORD'],
        "enable": True
    }
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/activedirectory/'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json()['job_id'], CLUSTER_IPS[0], 300)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    # Need to wait a little for cluster state to settle down

    for ip in CLUSTER_IPS:
        url = f'http://{ip}/api/v2.0/activedirectory/started'
        res = make_request('get', url)
        assert res.status_code == 200, f'ip: {ip}, res: {res.text}'
        assert res.json()

        url = f'http://{ip}/api/v2.0/activedirectory/get_state'
        res = make_request('get', url)
        assert res.status_code == 200, f'ip: {ip}, res: {res.text}'
        assert res.json() == 'HEALTHY'


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name="DS_ACCOUNTS_CONFIGURED")
def test_004_verify_ad_accounts_present(ip, request):
    depends(request, ['JOINED_AD'])

    payload = {"username": f'administrator@{CLUSTER_ADS["DOMAIN"]}'}
    url = f'http://{ip}/api/v2.0/user/get_user_obj/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    payload = {"groupname": fr'{CLUSTER_ADS["DOMAIN"]}\domain users'}
    url = f'http://{ip}/api/v2.0/group/get_group_obj/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_005_validate_cached_ad_accounts(ip, request):
    depends(request, ['DS_ACCOUNTS_CONFIGURED'])

    payload = {
        'query-filters': [["method", "=", "activedirectory.fill_cache"]],
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


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_006_validate_kerberos_settings(ip, request):
    depends(request, ['JOINED_AD'])

    payload = {
        'query-filters': [["realm", "=", CLUSTER_ADS['DOMAIN']]],
        'query-options': {'get': True},
    }
    url = f'http://{ip}/api/v2.0/kerberos/realm'
    res = make_request('get', url, data=payload)
    assert res.status_code == 200, res.text

    payload = {
        'query-filters': [["name", "=", 'AD_MACHINE_ACCOUNT']],
        'query-options': {'get': True},
    }
    url = f'http://{ip}/api/v2.0/kerberos/keytab'
    res = make_request('get', url, data=payload)
    assert res.status_code == 200, res.text

    # check that kinit succeeded
    payload = {
        'msg': 'method',
        'method': 'kerberos.check_ticket',
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res

    # check that keytab was generated
    payload = {
        'msg': 'method',
        'method': 'kerberos.keytab.kerberos_principal_choices',
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res
    assert len(res['result']) != 0, res


def test_007_validate_dns_records_added(request):
    depends(request, ['JOINED_AD'])

    payload = {
        'msg': 'method',
        'method': 'dnsclient.forward_lookup',
        'params': [{"names": [f'truenas.{CLUSTER_ADS["DOMAIN"]}']}],
    }
    res = make_ws_request(CLUSTER_IPS[0], payload)
    assert res.get('error') is None, res
    answers = set([x['address'] for x in res['result']])
    assert set(PUBLIC_IPS) == answers


@pytest.mark.dependency(name="DS_CLUSTER_SMB_SHARE_CREATED")
def test_008_create_clustered_smb_share(request):
    depends(request, ['JOINED_AD'])
    global ds_smb_share_id
    global ds_wrk

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/mkdir/'
    res = make_request('post', url, data=SHARE_FUSE_PATH)
    assert res.status_code == 200, res.text

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/user/get_user_obj/'
    payload = {"username": f'{CLUSTER_ADS["USERNAME"]}@{CLUSTER_ADS["DOMAIN"]}'}
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
        "comment": "AD clustered SMB share",
        "path": '/ds_smb_share_01',
        "name": "DS_CL_SMB",
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


@pytest.mark.dependency(name="DS_SMB_SHARE_IS_WRITABLE")
@pytest.mark.parametrize('ip', PUBLIC_IPS)
def test_009_share_is_writable_via_public_ips(ip, request):
    """
    This test creates creates an empty file, sets "delete on close" flag, then
    closes it. NTStatusError should be raised containing failure details
    if we are for some reason unable to access the share.

    This test will fail if smb.conf / smb4.conf does not exist on client / server running test.
    """
    depends(request, ['DS_CLUSTER_SMB_SHARE_CREATED'])

    with smb_connection(
        host=ip,
        share="DS_CL_SMB",
        username=CLUSTER_ADS['USERNAME'],
        domain=ds_wrk,
        password=CLUSTER_ADS['PASSWORD'],
        smb1=False
    ) as tcon:
        fd = tcon.create_file("testfile", "w")
        tcon.close(fd, True)


def test_010_xattrs_writable_via_smb(request):
    depends(request, ['DS_SMB_SHARE_IS_WRITABLE'])

    with smb_connection(
        host=PUBLIC_IPS[0],
        share="DS_CL_SMB",
        username=CLUSTER_ADS['USERNAME'],
        domain=ds_wrk,
        password=CLUSTER_ADS['PASSWORD'],
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
    depends(request, ['DS_CLUSTER_SMB_SHARE_CREATED'])

    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/sharing/smb/id/{ds_smb_share_id}'
    res = make_request('delete', url)
    assert res.status_code == 200, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_049_verify_clustered_share_removed(ip, request):
    depends(request, ['DS_CLUSTER_SMB_SHARE_CREATED'])

    url = f'http://{ip}/api/v2.0/sharing/smb?id={ds_smb_share_id}'
    res = make_request('get', url)
    assert res.status_code == 200, res.text
    assert res.json() == [], res.text

    cmd = f'rm -rf /cluster/{CLUSTER_INFO["GLUSTER_VOLUME"]}/ds_smb_share_01'
    res = ssh_test(CLUSTER_IPS[0], cmd)
    assert res['result'], res['output']


def test_050_leave_activedirectory(request):
    depends(request, ['JOINED_AD'])

    payload = {
        "username": CLUSTER_ADS['USERNAME'],
        "password": CLUSTER_ADS['PASSWORD']
    }
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/activedirectory/leave/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json(), CLUSTER_IPS[0], 300)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    for ip in CLUSTER_IPS:
        url = f'http://{ip}/api/v2.0/activedirectory/get_state'
        res = make_request('get', url)
        assert res.status_code == 200, f'ip: {ip}, res: {res.text}'
        assert res.json() == 'DISABLED'

        url = f'http://{ip}/api/v2.0/activedirectory/started'
        res = make_request('get', url)
        assert res.status_code == 200, f'ip: {ip}, res: {res.text}'
        assert res.json() is False
