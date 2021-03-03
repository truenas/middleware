#!/usr/bin/env python3

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE, PUT, SSH_TEST
from auto_config import ip, user, password, pool_name, scale, dev_test

reason = 'Skip for testing' if dev_test else 'Skipping test for Scale'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(scale or dev_test, reason=reason)

test1_dataset = f'{pool_name}/test1'
test2_dataset = f'{pool_name}/test2'


def test_01_verify_default_aclmode_from_pool_dataset_with_api(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/pool/dataset/id/{pool_name}/')
    assert results.status_code == 200, results.text
    assert results.json()['aclmode']['rawvalue'] == 'passthrough', results.text


def test_02_verify_default_aclmode_from_pool_dataset_with_zfs_get(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f"zfs get aclmode {pool_name}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'passthrough' in results['output'], results['output']


def test_03_create_test1_dataset_to_verify_inherit_parent_aclmode(request):
    depends(request, ["pool_04"], scope="session")
    result = POST(
        '/pool/dataset/', {
            'name': test1_dataset
        }
    )
    assert result.status_code == 200, result.text


def test_04_verify_test1_dataset_inherited_parent_aclmode_with_api(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/pool/dataset/id/{test1_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
    assert results.json()['aclmode']['rawvalue'] == 'passthrough', results.text


def test_05_verify_test1_dataset_inherited_parent_aclmode_with_zfs_get(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f"zfs get aclmode {test1_dataset}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'passthrough' in results['output'], results['output']


def test_06_change_the_default_aclmode_of_the_pool_dataset_to_restricted(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        'aclmode': 'RESTRICTED'
    }
    results = PUT(f'/pool/dataset/id/{pool_name}/', payload)
    assert results.status_code == 200, results.text


def test_07_verify_the_pool_dataset_aclmode_changed_to_restricted_with_api(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/pool/dataset/id/{pool_name}/')
    assert results.status_code == 200, results.text
    assert results.json()['aclmode']['rawvalue'] == 'restricted', results.text


def test_08_verify_the_pool_dataset_aclmode_changed_to_restricted_with_zfs_get(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f"zfs get aclmode {pool_name}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'restricted' in results['output'], results['output']


def test_09_verify_test1_dataset_inherited_parent_aclmode_changes_with_api(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/pool/dataset/id/{test1_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
    assert results.json()['aclmode']['rawvalue'] == 'restricted', results.text


def test_10_verify_test1_dataset_inherited_parent_aclmode_changes_with_zfs_get(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f"zfs get aclmode {test1_dataset}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'restricted' in results['output'], results['output']


def test_11_create_test2_dataset_to_verify_inherit_parent_aclmode(request):
    depends(request, ["pool_04"], scope="session")
    result = POST(
        '/pool/dataset/', {
            'name': test2_dataset
        }
    )
    assert result.status_code == 200, result.text


def test_12_verify_test2_dataset_inherited_parent_restricted_aclmode_with_api(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/pool/dataset/id/{test2_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
    assert results.json()['aclmode']['rawvalue'] == 'restricted', results.text


def test_13_verify_test2_dataset_inherited_parent_restricted_aclmode_with_zfs_get(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f"zfs get aclmode {test2_dataset}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'restricted' in results['output'], results['output']


def test_14_change_the_pool_dataset_aclmode_back_to_passthrough(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        'aclmode': 'PASSTHROUGH'
    }
    results = PUT(f'/pool/dataset/id/{pool_name}/', payload)
    assert results.status_code == 200, results.text


def test_15_verify_test1_dataset_inherited_parent_aclmode_changes_with_api(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/pool/dataset/id/{test1_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
    assert results.json()['aclmode']['rawvalue'] == 'passthrough', results.text


def test_16_verify_test1_dataset_inherited_parent_aclmode_changes_with_zfs_get(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f"zfs get aclmode {test1_dataset}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'passthrough' in results['output'], results['output']


def test_17_verify_test2_dataset_inherited_parent_aclmode_changes_with_api(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/pool/dataset/id/{test2_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
    assert results.json()['aclmode']['rawvalue'] == 'passthrough', results.text


def test_18_verify_test2_dataset_inherited_parent_aclmode_changes_with_zfs_get(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f"zfs get aclmode {test2_dataset}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'passthrough' in results['output'], results['output']


def test_19_verify_the_pool_dataset_aclmode_changed_to_passthrough_with_api(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/pool/dataset/id/{pool_name}/')
    assert results.status_code == 200, results.text
    assert results.json()['aclmode']['rawvalue'] == 'passthrough', results.text


def test_20_verify_the_pool_dataset_aclmode_changed_to_passthrough_with_zfs_get(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f"zfs get aclmode {pool_name}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'passthrough' in results['output'], results['output']


def test_21_change_test1_dataset_aclmode_to_restricted(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        'aclmode': 'RESTRICTED'
    }
    results = PUT(f'/pool/dataset/id/{test1_dataset.replace("/", "%2F")}/', payload)
    assert results.status_code == 200, results.text


def test_22_verify_test1_dataset_aclmode_changed_to_restricted_with_api(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/pool/dataset/id/{test1_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
    assert results.json()['aclmode']['rawvalue'] == 'restricted', results.text


def test_23_verify_test1_dataset_aclmode_changed_to_restricted_with_zfs_get(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f"zfs get aclmode {test1_dataset}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'restricted' in results['output'], results['output']


def test_24_delete_test1_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f'/pool/dataset/id/{test1_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text


def test_25_delete_test2_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f'/pool/dataset/id/{test2_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
