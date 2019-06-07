#!/usr/bin/env python3.6

# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, PUT
from auto_config import pool_name

dataset = f'{pool_name}/dataset1'
dataset_url = dataset.replace('/', '%2F')


def test_01_check_dataset_endpoint():
    assert isinstance(GET('/pool/dataset/').json(), list)


def test_02_create_dataset():
    result = POST(
        '/pool/dataset/', {
            'name': dataset
        }
    )
    assert result.status_code == 200, result.text


def test_03_query_dataset_by_name():
    dataset = GET(f'/pool/dataset/?id={dataset_url}')

    assert isinstance(dataset.json()[0], dict)


def test_04_update_dataset_description():
    result = PUT(
        f'/pool/dataset/id/{dataset_url}/', {
            'comments': 'testing dataset'
        }
    )

    assert result.status_code == 200, result.text


def test_05_set_permissions_for_dataset():
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': [],
            'mode': '777',
            'group': 'nobody',
            'user': 'nobody'
        }
    )

    assert result.status_code == 200, result.text


def test_06_promoting_dataset():
    # TODO: ONCE WE HAVE MANUAL SNAPSHOT FUNCTIONAITY IN MIDDLEWARED,
    # THIS TEST CAN BE COMPLETED THEN
    pass

# Test 07 through 11 verify basic ACL functionality. A default ACL is
# set, verified, stat output checked for its presence. Then ACL is removed
# and stat output confirms its absence.

def test_07_set_acl_for_dataset():
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': default_acl,
            'group': 'nobody',
            'user': 'nobody'
        }
    )

    assert result.status_code == 200, result.text


def test_08_filesystem_getacl():
    results = POST('/filesystem/getacl/', {'path': f'/mnt/{dataset}', 'simplified': True})
    assert results.status_code == 200, results.text
    for key in ['tag', 'type', 'perms', 'flags']:
        assert results.json()['acl'][0][key] == default_acl[0][key], results.text
        assert results.json()['acl'][1][key] == default_acl[1][key], results.text


def test_09_filesystem_acl_is_present():
    results = POST('/filesystem/stat/', f'/mnt/{dataset}')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] == True, results.text


def test_10_strip_acl_from_dataset():
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': [],
            'mode': '777',
            'group': 'nobody',
            'user': 'nobody',
            'options': {'stripacl': True}
        }
    )

    assert result.status_code == 200, result.text


def test_11_filesystem_acl_is_removed():
    results = POST('/filesystem/stat/', f'/mnt/{dataset}')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] == False, results.text
    assert oct(results.json()['mode']) == '0o40777', results.text


def test_12_delete_dataset():
    result = DELETE(
        f'/pool/dataset/id/{dataset_url}/'
    )
    assert result.status_code == 200, result.text
