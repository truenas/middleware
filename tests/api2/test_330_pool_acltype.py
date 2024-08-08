#!/usr/bin/env python3

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name
from functions import POST, GET, PUT, DELETE, SSH_TEST
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.assets.pool import dataset as make_dataset

test1_dataset = f'{pool_name}/test1'
dataset_url = test1_dataset.replace("/", "%2F")


@pytest.fixture(scope='module')
def create_test_dataset():
    with make_dataset('test1') as ds:
        yield ds


def test_01_verify_default_acltype_from_pool_dataset_with_api(request):
    results = GET(f'/pool/dataset/id/{pool_name}/')
    assert results.status_code == 200, results.text
    assert results.json()['acltype']['rawvalue'] == 'posix', results.text


def test_04_verify_test1_dataset_inherited_parent_acltype_with_api(create_test_dataset, request):
    results = GET(f'/pool/dataset/id/{dataset_url}/')
    assert results.status_code == 200, results.text
    assert results.json()['acltype']['rawvalue'] == 'posix', results.text


def test_06_change_acltype_to_nfsv4(create_test_dataset, request):
    call('pool.dataset.update', test1_dataset, {
        'acltype': 'NFSV4', 'aclmode': 'PASSTHROUGH'
    })

    res = call('zfs.dataset.query', [['id', '=', test1_dataset]],
        {'get': True, 'extra': {'retrieve_children': False}}
    )
    props = res['properties']

    assert props['acltype']['value'] == 'nfsv4', str(props)
    assert props['aclmode']['value'] == 'passthrough', str(props)
    assert props['aclinherit']['value'] == 'passthrough', str(props)


def test_07_reset_acltype_to_posix(create_test_dataset, request):
    call('pool.dataset.update', test1_dataset, {
        'acltype': 'POSIX', 'aclmode': 'DISCARD'
    })

    res = call('zfs.dataset.query', [['id', '=', test1_dataset]],
        {'get': True, 'extra': {'retrieve_children': False}}
    )
    props = res['properties']

    assert props['acltype']['value'] == 'posix', str(props)
    assert props['aclmode']['value'] == 'discard', str(props)
    assert props['aclinherit']['value'] == 'discard', str(props)
