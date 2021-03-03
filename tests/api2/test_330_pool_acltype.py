#!/usr/bin/env python3

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE, SSH_TEST
from auto_config import ip, user, password, pool_name, scale, dev_test

reason = 'Skip for testing' if dev_test else 'Skipping test for Core and Enterprise'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(scale is False or dev_test, reason=reason)
test1_dataset = f'{pool_name}/test1'


def test_01_verify_default_acltype_from_pool_dataset_with_api(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/pool/dataset/id/{pool_name}/')
    assert results.status_code == 200, results.text
    assert results.json()['acltype']['rawvalue'] == 'posix', results.text


def test_02_verify_default_acltype_from_pool_dataset_with_zfs_get(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f"zfs get acltype {pool_name}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'posix' in results['output'], results['output']


def test_03_create_test1_dataset_to_verify_inherit_parent_acltype(request):
    depends(request, ["pool_04"], scope="session")
    result = POST(
        '/pool/dataset/', {
            'name': test1_dataset
        }
    )
    assert result.status_code == 200, result.text


def test_04_verify_test1_dataset_inherited_parent_acltype_with_api(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f'/pool/dataset/id/{test1_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
    assert results.json()['acltype']['rawvalue'] == 'posix', results.text


def test_05_verify_test1_dataset_inherited_parent_acltype_with_zfs_get(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f"zfs get acltype {test1_dataset}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'posix' in results['output'], results['output']


def test_06_delete_test1_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f'/pool/dataset/id/{test1_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
