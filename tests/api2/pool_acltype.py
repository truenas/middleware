#!/usr/bin/env python3

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE, SSH_TEST
from auto_config import ip, user, password, pool_name

test1_dataset = f'{pool_name}/test1'


# off will need to replace posixacl in the future
def test_01_verify_default_acltype_from_pool_dataset_with_api():
    results = GET(f'/pool/dataset/id/{pool_name}/')
    assert results.status_code == 200, results.text
    assert results.json()['acltype']['rawvalue'] == 'off', results.text


# off will need to replace posixacl in the future
def test_02_verify_default_acltype_from_pool_dataset_with_zfs_get():
    cmd = f"zfs get acltype {pool_name}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'off' in results['output'], results['output']


def test_03_create_test1_dataset_to_verify_inherit_parent_acltype():
    result = POST(
        '/pool/dataset/', {
            'name': test1_dataset
        }
    )
    assert result.status_code == 200, result.text


def test_04_verify_test1_dataset_inherited_parent_acltype_with_api():
    results = GET(f'/pool/dataset/id/{test1_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
    assert results.json()['acltype']['rawvalue'] == 'posixacl', results.text


def test_05_verify_test1_dataset_inherited_parent_acltype_with_zfs_get():
    cmd = f"zfs get acltype {test1_dataset}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'posixacl' in results['output'], results['output']


def test_06_delete_test1_dataset():
    results = DELETE(f'/pool/dataset/id/{test1_dataset.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
