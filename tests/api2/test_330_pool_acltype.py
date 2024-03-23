#!/usr/bin/env python3

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, PUT, DELETE, SSH_TEST, make_ws_request
from auto_config import ip, user, password, pool_name

test1_dataset = f'{pool_name}/test1'
dataset_url = test1_dataset.replace("/", "%2F")

pytestmark = pytest.mark.zfs


def test_01_verify_default_acltype_from_pool_dataset_with_api(request):
    results = GET(f'/pool/dataset/id/{pool_name}/')
    assert results.status_code == 200, results.text
    assert results.json()['acltype']['rawvalue'] == 'posix', results.text


def test_02_verify_default_acltype_from_pool_dataset_with_zfs_get(request):
    cmd = f"zfs get acltype {pool_name}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'posix' in results['output'], results['output']


def test_03_create_test1_dataset_to_verify_inherit_parent_acltype(request):
    result = POST(
        '/pool/dataset/', {
            'name': test1_dataset
        }
    )
    assert result.status_code == 200, result.text


def test_04_verify_test1_dataset_inherited_parent_acltype_with_api(request):
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['acltype']['rawvalue'] == 'posix', results.text


def test_05_verify_test1_dataset_inherited_parent_acltype_with_zfs_get(request):
    cmd = f"zfs get acltype {test1_dataset}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'posix' in results['output'], results['output']


def test_06_change_acltype_to_nfsv4(request):
    result = PUT(
        f'/pool/dataset/id/{dataset_url}/', {
            'acltype': 'NFSV4',
            'aclmode': 'PASSTHROUGH'
        }
    )
    assert result.status_code == 200, result.text

    payload = {
        'msg': 'method',
        'method': 'zfs.dataset.query',
        'params': [
            [['id', '=', test1_dataset]],
            {'get': True, 'extra': {'retrieve_children': False}}
        ]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, str(res['error'])
    props = res['result']['properties']

    assert props['acltype']['value'] == 'nfsv4', str(props)
    assert props['aclmode']['value'] == 'passthrough', str(props)
    assert props['aclinherit']['value'] == 'passthrough', str(props)


def test_07_reset_acltype_to_posix(request):
    result = PUT(
        f'/pool/dataset/id/{dataset_url}/', {
            'acltype': 'POSIX',
            'aclmode': 'DISCARD'
        }
    )
    assert result.status_code == 200, result.text


    payload = {
        'msg': 'method',
        'method': 'zfs.dataset.query',
        'params': [
            [['id', '=', test1_dataset]],
            {'get': True, 'extra': {'retrieve_children': False}}
        ]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, str(res['error'])
    props = res['result']['properties']

    assert props['acltype']['value'] == 'posix', str(props)
    assert props['aclmode']['value'] == 'discard', str(props)
    assert props['aclinherit']['value'] == 'discard', str(props)


def test_08_delete_test1_dataset(request):
    results = DELETE(f'/pool/dataset/id/{test1_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
