#!/usr/bin/env python3

# License: BSD

import errno

import pytest
from middlewared.client import ClientException
from middlewared.service_exception import CallError
from middlewared.test.integration.assets.pool import dataset as dataset_asset
from middlewared.test.integration.utils import call
from pytest_dependency import depends
from test_011_user import UserAssets

from auto_config import password, pool_name, user
from functions import DELETE, GET, POST, PUT, SSH_TEST, wait_on_job

dataset = f'{pool_name}/dataset1'
dataset_url = dataset.replace('/', '%2F')
zvol = f'{pool_name}/zvol1'
zvol_url = zvol.replace('/', '%2F')

default_acl = [
    {
        "tag": "owner@",
        "id": None,
        "type": "ALLOW",
        "perms": {"BASIC": "FULL_CONTROL"},
        "flags": {"BASIC": "INHERIT"}
    },
    {
        "tag": "group@",
        "id": None,
        "type": "ALLOW",
        "perms": {"BASIC": "FULL_CONTROL"},
        "flags": {"BASIC": "INHERIT"}
    }
]


def test_01_check_dataset_endpoint(request):
    assert isinstance(GET('/pool/dataset/').json(), list)


def test_02_create_dataset(request):
    result = POST(
        '/pool/dataset/', {
            'name': dataset,
            "acltype": "NFSV4",
            "aclmode": "PASSTHROUGH"
        }
    )
    assert result.status_code == 200, result.text


def test_03_query_dataset_by_name(request):
    dataset = GET(f'/pool/dataset/?id={dataset_url}')

    assert isinstance(dataset.json()[0], dict)


def test_04_update_dataset_description(request):
    result = PUT(
        f'/pool/dataset/id/{dataset_url}/', {
            'comments': 'testing dataset'
        }
    )

    assert result.status_code == 200, result.text


def test_05_set_permissions_for_dataset(request):
    global JOB_ID
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': [],
            'mode': '777',
            'group': 'nogroup',
            'user': 'nobody'
        }
    )

    assert result.status_code == 200, result.text
    JOB_ID = result.json()


def test_06_verify_job_id_is_successfull(request):
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_07_promoting_dataset(request):
    # TODO: ONCE WE HAVE MANUAL SNAPSHOT FUNCTIONAITY IN MIDDLEWARED,
    # THIS TEST CAN BE COMPLETED THEN
    pass

# Test 07 through 11 verify basic ACL functionality. A default ACL is
# set, verified, stat output checked for its presence. Then ACL is removed
# and stat output confirms its absence.


@pytest.mark.dependency(name="pool_dataset_08")
def test_08_set_acl_for_dataset(request):
    global JOB_ID
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': default_acl,
            'group': 'nogroup',
            'user': 'nobody'
        }
    )

    assert result.status_code == 200, result.text
    JOB_ID = result.json()


@pytest.mark.dependency(name="acl_pool_perm_09")
def test_09_verify_job_id_is_successfull(request):
    depends(request, ["pool_dataset_08"], scope="session")
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_10_get_filesystem_getacl(request):
    depends(request, ["acl_pool_perm_09"], scope="session")
    global results
    payload = {
        'path': f'/mnt/{dataset}',
        'simplified': True
    }
    results = POST('/filesystem/getacl/', payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('key', ['tag', 'type', 'perms', 'flags'])
def test_11_verify_filesystem_getacl(request, key):
    depends(request, ["acl_pool_perm_09"], scope="session")
    assert results.json()['acl'][0][key] == default_acl[0][key], results.text
    assert results.json()['acl'][1][key] == default_acl[1][key], results.text


def test_12_filesystem_acl_is_present(request):
    depends(request, ["acl_pool_perm_09"], scope="session")
    results = POST('/filesystem/stat/', f'/mnt/{dataset}')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is True, results.text


def test_13_strip_acl_from_dataset(request):
    global JOB_ID
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': [],
            'mode': '777',
            'group': 'nogroup',
            'user': 'nobody',
            'options': {'stripacl': True}
        }
    )

    assert result.status_code == 200, result.text
    JOB_ID = result.json()


def test_14_setting_various_quotas(request):
    depends(request, [UserAssets.ShareUser01['depends_name']], scope='session')
    user = group = 'shareuser'
    user_gid = GET('/group/?group=shareuser').json()[0]['gid']
    user_uid = GET('/user/?username=shareuser').json()[0]['uid']
    user_quota_value = 1000000
    group_quota_value = user_quota_value * 2
    dataset_quota_value = group_quota_value + 10000
    dataset_refquota_value = dataset_quota_value + 10000

    set_quota_payload = [
        {'quota_type': 'USER', 'id': user, 'quota_value': user_quota_value},
        {'quota_type': 'USEROBJ', 'id': user, 'quota_value': user_quota_value},
        {'quota_type': 'GROUP', 'id': group, 'quota_value': group_quota_value},
        {'quota_type': 'GROUPOBJ', 'id': group, 'quota_value': group_quota_value},
        {'quota_type': 'DATASET', 'id': 'QUOTA', 'quota_value': dataset_quota_value},
        {'quota_type': 'DATASET', 'id': 'REFQUOTA', 'quota_value': dataset_refquota_value},
    ]
    results = POST(f'/pool/dataset/id/{dataset_url}/set_quota', set_quota_payload)
    assert results.status_code == 200, results.text

    expected_user_quota_result = {
        'quota_type': 'USER',
        'id': user_uid,
        'quota': user_quota_value,
        'obj_quota': user_quota_value,
        'name': user
    }
    results = POST(f'/pool/dataset/id/{dataset_url}/get_quota', {'quota_type': 'USER'})
    assert results.status_code == 200, results.text
    assert any((i == expected_user_quota_result for i in results.json())), results

    expected_group_quota_result = {
        'quota_type': 'GROUP',
        'id': user_gid,
        'quota': group_quota_value,
        'obj_quota': group_quota_value,
        'name': group
    }
    results = POST(f'/pool/dataset/id/{dataset_url}/get_quota', {'quota_type': 'GROUP'})
    assert results.status_code == 200, results.text
    assert any((i == expected_group_quota_result for i in results.json())), results

    expected_dataset_quota_result = {
        'quota_type': 'DATASET',
        'id': dataset,
        'name': dataset,
        'quota': dataset_quota_value,
        'refquota': dataset_refquota_value,
    }
    results = POST(f'/pool/dataset/id/{dataset_url}/get_quota', {'quota_type': 'DATASET'})
    assert results.status_code == 200, results.text
    for ds_quota in filter(lambda x: x['id'] == expected_dataset_quota_result['id'], results.json()):
        # the dataset quota that is return includes a used_bytes key that has an actual
        # filesystem value. We can't predict what that value will ever be at this point
        # so we just verify all the other keys match what we expect
        assert all((expected_dataset_quota_result[k] == ds_quota[k] for k in expected_dataset_quota_result))


def test_16_verify_job_id_is_successfull(request):
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_17_filesystem_acl_is_removed(request):
    results = POST('/filesystem/stat/', f'/mnt/{dataset}')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is False, results.text
    assert oct(results.json()['mode']) == '0o40777', results.text


def test_18_delete_dataset(request):
    result = DELETE(
        f'/pool/dataset/id/{dataset_url}/'
    )
    assert result.status_code == 200, result.text


def test_19_verify_the_id_dataset_does_not_exist(request):
    result = GET(f'/pool/dataset/id/{dataset_url}/')
    assert result.status_code == 404, result.text


def test_20_creating_zvol(request):
    global results, payload
    payload = {
        'name': zvol,
        'type': 'VOLUME',
        'volsize': 163840,
        'volblocksize': '16K'
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('key', ['name', 'type', 'volsize', 'volblocksize'])
def test_21_verify_output(request, key):
    if key == 'volsize':
        assert results.json()[key]['parsed'] == payload[key], results.text
    elif key == 'volblocksize':
        assert results.json()[key]['value'] == payload[key], results.text
    else:
        assert results.json()[key] == payload[key], results.text


def test_22_query_zvol_by_id(request):
    global results
    results = GET(f'/pool/dataset/id/{zvol_url}')
    assert isinstance(results.json(), dict)


@pytest.mark.parametrize('key', ['name', 'type', 'volsize', 'volblocksize'])
def test_23_verify_the_query_zvol_output(request, key):
    if key == 'volsize':
        assert results.json()[key]['parsed'] == payload[key], results.text
    elif key == 'volblocksize':
        assert results.json()[key]['value'] == payload[key], results.text
    else:
        assert results.json()[key] == payload[key], results.text


def test_24_update_zvol(request):
    global payload, results
    payload = {
        'volsize': 163840,
        'comments': 'testing zvol'
    }
    result = PUT(f'/pool/dataset/id/{zvol_url}/', payload)
    assert result.status_code == 200, result.text


@pytest.mark.parametrize('key', ['volsize'])
def test_25_verify_update_zvol_output(request, key):
    assert results.json()[key]['parsed'] == payload[key], results.text


def test_26_query_zvol_changes_by_id(request):
    global results
    results = GET(f'/pool/dataset/id/{zvol_url}')
    assert isinstance(results.json(), dict), results


@pytest.mark.parametrize('key', ['comments', 'volsize'])
def test_27_verify_the_query_change_zvol_output(request, key):
    assert results.json()[key]['parsed'] == payload[key], results.text


def test_28_delete_zvol(request):
    result = DELETE(f'/pool/dataset/id/{zvol_url}/')
    assert result.status_code == 200, result.text


def test_29_verify_the_id_zvol_does_not_exist(request):
    result = GET(f'/pool/dataset/id/{zvol_url}/')
    assert result.status_code == 404, result.text


@pytest.mark.parametrize("create_dst", [True, False])
def test_30_delete_dataset_with_receive_resume_token(request, create_dst):
    result = POST('/pool/dataset/', {'name': f'{pool_name}/src'})
    assert result.status_code == 200, result.text

    if create_dst:
        result = POST('/pool/dataset/', {'name': f'{pool_name}/dst'})
        assert result.status_code == 200, result.text

    results = SSH_TEST(f'dd if=/dev/urandom of=/mnt/{pool_name}/src/blob bs=1M count=1', user, password)
    assert results['result'] is True, results
    results = SSH_TEST(f'zfs snapshot {pool_name}/src@snap-1', user, password)
    assert results['result'] is True, results
    results = SSH_TEST(f'zfs send {pool_name}/src@snap-1 | head -c 102400 | zfs recv -s -F {pool_name}/dst', user, password)
    results = SSH_TEST(f'zfs get -H -o value receive_resume_token {pool_name}/dst', user, password)
    assert results['result'] is True, results
    assert results['stdout'].strip() != "-", results

    result = DELETE(f'/pool/dataset/id/{pool_name}%2Fsrc/', {
        'recursive': True,
    })
    assert result.status_code == 200, result.text
    if create_dst:
        result = DELETE(f'/pool/dataset/id/{pool_name}%2Fdst/', {
            'recursive': True,
        })
        assert result.status_code == 200, result.text


def test_31_path_to_dataset(request):
    """
    This test is to check results of private method to convert
    a path to a dataset name. Return is expected to be None if the
    path points to the boot pool.
    """

    assert call('zfs.dataset.path_to_dataset', f'/mnt/{pool_name}') == pool_name

    with pytest.raises(CallError) as ve:
        call('zfs.dataset.path_to_dataset', '/mnt')

    assert 'path is on boot pool' in str(ve.value)


def test_32_test_apps_preset(request):
    with dataset_asset('APPS_TEST', {'share_type': 'APPS'}) as ds:
        ds = call('pool.dataset.get_instance', ds)

        assert ds['acltype']['value'] == 'NFSV4'
        assert ds['atime']['value'] == 'OFF'
        assert ds['aclmode']['value'] == 'PASSTHROUGH'

        results = POST('/filesystem/getacl/', {'path': ds['mountpoint']})
        assert results.status_code == 200, results.text

        acl = results.json()['acl']
        assert any([ace['id'] == 568 for ace in acl]), str(acl)


def test_33_simplified_charts_api(request):
    def check_for_entry(acl, id_type, xid, perms, is_posix=False):
        has_entry = False
        has_default = False
        has_access = False

        for ace in acl:
            if ace['id'] == xid and ace['tag'] == id_type and ace['perms'] == perms:
                if is_posix:
                    if ace['default']:
                        assert has_default is False
                        has_default = True
                    else:
                        assert has_access is False
                        has_access = True

                else:
                    assert has_entry is False
                    has_entry = True

        return has_entry or (has_access and has_default)

    USER_TO_ADD = 8765309
    USER2_TO_ADD = 8765310
    GROUP_TO_ADD = 1138
    NFS4_ACL_PAYLOAD = [
        {'id_type': 'USER', 'id': USER_TO_ADD, 'access': 'MODIFY'},
        {'id_type': 'GROUP', 'id': GROUP_TO_ADD, 'access': 'READ'},
        {'id_type': 'USER', 'id': USER2_TO_ADD, 'access': 'FULL_CONTROL'},
    ]
    ACL_PAYLOAD = [
        {'id_type': 'USER', 'id': USER_TO_ADD, 'access': 'MODIFY'},
        {'id_type': 'GROUP', 'id': GROUP_TO_ADD, 'access': 'READ'},
        {'id_type': 'USER', 'id': USER_TO_ADD, 'access': 'FULL_CONTROL'},
    ]

    # TEST NFS4 ACL type
    with dataset_asset('APPS_NFS4', {'share_type': 'APPS'}) as ds:
        call('filesystem.add_to_acl', {
            'path': f'/mnt/{ds}',
            'entries': NFS4_ACL_PAYLOAD
        }, job=True)

        results = POST('/filesystem/getacl/', {'path': f'/mnt/{ds}'})
        assert results.status_code == 200, results.text

        acl = results.json()['acl']
        assert check_for_entry(acl, 'USER', USER_TO_ADD, {'BASIC': 'MODIFY'}), str(acl)
        assert check_for_entry(acl, 'GROUP', GROUP_TO_ADD, {'BASIC': 'READ'}), str(acl)
        assert check_for_entry(acl, 'USER', USER2_TO_ADD, {'BASIC': 'FULL_CONTROL'}), str(acl)

        # check behavior of using force option.
        # presence of file in path should trigger failure
        # if force is not set
        results = SSH_TEST(f'touch /mnt/{ds}/canary', user, password)
        assert results['result'] is True, results

        with pytest.raises(ClientException) as ve:
            call('filesystem.add_to_acl', {
                'path': f'/mnt/{ds}',
                'entries': NFS4_ACL_PAYLOAD
            }, job=True)
            assert ve.value.errno == errno.EPERM

        # check behavior of using force option.
        # second call with `force` specified should succeed
        call('filesystem.add_to_acl', {
            'path': f'/mnt/{ds}',
            'entries': NFS4_ACL_PAYLOAD,
            'options': {'force': True}
        }, job=True)

        # we already added the entry earlier.
        # this check makes sure we're not adding duplicate entries.
        results = POST('/filesystem/getacl/', {'path': f'/mnt/{ds}'})
        assert results.status_code == 200, results.text

        acl = results.json()['acl']
        assert check_for_entry(acl, 'USER', USER_TO_ADD, {'BASIC': 'MODIFY'}), str(acl)
        assert check_for_entry(acl, 'GROUP', GROUP_TO_ADD, {'BASIC': 'READ'}), str(acl)
        assert check_for_entry(acl, 'USER', USER2_TO_ADD, {'BASIC': 'FULL_CONTROL'}), str(acl)

    with dataset_asset('APPS_POSIX') as ds:
        call('filesystem.add_to_acl', {
            'path': f'/mnt/{ds}',
            'entries': ACL_PAYLOAD
        }, job=True)

        results = POST('/filesystem/getacl/', {'path': f'/mnt/{ds}'})
        assert results.status_code == 200, results.text

        acl = results.json()['acl']
        assert check_for_entry(acl, 'USER', USER_TO_ADD, {'READ': True, 'WRITE': True, 'EXECUTE': True}, True), str(acl)
        assert check_for_entry(acl, 'GROUP', GROUP_TO_ADD, {'READ': True, 'WRITE': False, 'EXECUTE': True}, True), str(acl)


def test_34_multiprotocol_share_type_preset(request):
    with dataset_asset('MULTIPROTOCOL', {'share_type': 'MULTIPROTOCOL'}) as ds:
        ds = call('pool.dataset.get_instance', ds)

        assert ds['acltype']['value'] == 'NFSV4'
        assert ds['aclmode']['value'] == 'PASSTHROUGH'
        assert ds['casesensitivity']['value'] == 'SENSITIVE'
        assert ds['atime']['value'] == 'OFF'


def test_35_create_ancestors(request):
    with dataset_asset('foo/bar/tar', {'share_type': 'SMB', 'create_ancestors': True}) as ds:
        ds = call('pool.dataset.get_instance', ds)

        assert ds['acltype']['value'] == 'NFSV4'
        assert ds['aclmode']['value'] == 'RESTRICTED'
        st = call('filesystem.stat', ds['mountpoint'])
        assert st['acl'] is True, str(st)


def test_36_nested_smb_dataset(request):
    with dataset_asset('parent', {'share_type': 'GENERIC'}) as d:
        ds = call('pool.dataset.get_instance', d)
        assert ds['acltype']['value'] == 'POSIX'
        assert ds['aclmode']['value'] == 'DISCARD'

        with dataset_asset('parent/child', {'share_type': 'SMB'}) as d:
            ds = call('pool.dataset.get_instance', d)
            assert ds['acltype']['value'] == 'NFSV4'
            assert ds['aclmode']['value'] == 'RESTRICTED'
