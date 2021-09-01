#!/usr/bin/env python3

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, PUT, DELETE
from auto_config import pool_name, dev_test

reason = 'Skip for testing' if dev_test else 'Skipping test for Core and Enterprise'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='dev-test')


@pytest.mark.dependency(name="ACLTEMPLATE_DATASETS_CREATED")
@pytest.mark.parametrize('acltype', ['NFSV4', 'POSIX'])
def test_01_create_test_datasets(request, acltype):
    """
    Setup of datasets for testing templates.
    This test shouldn't fail unless pool.dataset endpoint is
    thoroughly broken.
    """
    depends(request, ["pool_04"], scope="session")
    result = POST(
        '/pool/dataset/', {
            'name': f'{pool_name}/acltemplate_{acltype.lower()}',
            'acltype': acltype
        }
    )

    assert result.status_code == 200, result.text


@pytest.mark.parametrize('acltype', ['NFSV4', 'POSIX'])
def test_02_check_builtin_types_by_path(request, acltype):
    """
    This test verifies that we can query builtins by paths, and
    that the acltype of the builtins matches that of the
    underlying path.
    """
    depends(request, ["ACLTEMPLATE_DATASETS_CREATED"], scope="session")
    expected_acltype = 'POSIX1E' if acltype == 'POSIX' else 'NFS4'
    payload = {
        'path': f'/mnt/{pool_name}/acltemplate_{acltype.lower()}',
    }
    results = POST('/filesystem/acltemplate/by_path', payload)
    assert results.status_code == 200, results.text
    for entry in results.json():
        assert entry['builtin'], results.text
        assert entry['acltype'] == expected_acltype, results.text


@pytest.mark.dependency(name="NEW_ACLTEMPLATES_CREATED")
@pytest.mark.parametrize('acltype', ['NFS4', 'POSIX'])
def test_03_create_new_template(request, acltype):
    """
    This method queries an existing builtin and creates a
    new acltemplate based on the data. Test of new ACL template
    insertion.
    """
    depends(request, ["ACLTEMPLATE_DATASETS_CREATED"], scope="session")
    results = GET(
        '/filesystem/acltemplate', payload={
            'query-filters': [['name', '=', f'{acltype}_RESTRICTED']],
            'query-options': {'get': True},
        }
    )
    assert results.status_code == 200, results.text

    acl = results.json()['acl']
    for entry in acl:
        if entry['id'] is None:
            entry['id'] = -1

    payload = {
        'name': f'{acltype}_TEST',
        'acl': acl,
        'acltype': results.json()['acltype']
    }

    results = POST('/filesystem/acltemplate', payload)
    assert results.status_code == 200, results.text
 

def test_04_legacy_check_default_acl_choices(request):
    """
    Verify that our new templates appear as choices for "default" ACLs.
    """
    depends(request, ["NEW_ACLTEMPLATES_CREATED"], scope="session")

    results = GET(
        '/filesystem/acltemplate', payload={
            'query-filters': [['builtin', '=', False]],
        }
    )
    assert results.status_code == 200, results.text

    names = [x['name'] for x in results.json()]

    results = POST('/filesystem/default_acl_choices')
    assert results.status_code == 200, results.text
    acl_choices = results.json()

    for name in names:
        assert name in acl_choices, results.text


@pytest.mark.parametrize('acltype', ['NFS4', 'POSIX'])
def test_05_legacy_check_default_acl_choices_by_path(request, acltype):
    """
    Verify that our new templates appear as choices for "default" ACLs
    given a path.
    """
    depends(request, ["NEW_ACLTEMPLATES_CREATED"], scope="session")
    inverse = 'POSIX' if acltype == 'NFS4' else 'NFS4'

    path = f'/mnt/{pool_name}/acltemplate_{"posix" if acltype == "POSIX" else "nfsv4"}'
    results = POST('/filesystem/default_acl_choices', payload=path)
    assert results.status_code == 200, results.text

    choices = results.json()
    assert f'{acltype}_TEST' in choices, results.text
    assert f'{inverse}_TEST' not in choices, results.text


@pytest.mark.dependency(name="NEW_ACLTEMPLATES_UPDATED")
@pytest.mark.parametrize('acltype', ['NFS4', 'POSIX'])
def test_09_update_new_template(request, acltype):
    """
    Rename the template we created to validated that `update`
    method works.
    """
    depends(request, ["NEW_ACLTEMPLATES_CREATED"], scope="session")
    results = GET(
        '/filesystem/acltemplate', payload={
            'query-filters': [['name', '=', f'{acltype}_TEST']],
            'query-options': {'get': True},
        }
    )

    assert results.status_code == 200, results.text

    payload = results.json()
    id = payload.pop('id')
    payload.pop('builtin')
    payload['name'] = f'{payload["name"]}2'

    results = PUT(f'/filesystem/acltemplate/id/{id}/', payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('acltype', ['NFS4', 'POSIX'])
def test_10_delete_new_template(request, acltype):
    depends(request, ["NEW_ACLTEMPLATES_UPDATED"], scope="session")
    results = GET(
        '/filesystem/acltemplate', payload={
            'query-filters': [['name', '=', f'{acltype}_TEST2']],
            'query-options': {'get': True},
        }
    )
    assert results.status_code == 200, results.text

    results = DELETE(f'/filesystem/acltemplate/id/{results.json()["id"]}')
    assert results.status_code == 200, results.text


def test_40_knownfail_builtin_delete(request):
    results = GET(
        '/filesystem/acltemplate', payload={
            'query-filters': [['builtin', '=', True]],
            'query-options': {'get': True},
        }
    )
    assert results.status_code == 200, results.text
    id = results.json()['id']

    results = DELETE(f'/filesystem/acltemplate/id/{id}')
    assert results.status_code == 422, results.text


def test_41_knownfail_builtin_update(request):
    results = GET(
        '/filesystem/acltemplate', payload={
            'query-filters': [['builtin', '=', True]],
            'query-options': {'get': True},
        }
    )
    assert results.status_code == 200, results.text
    payload = results.json()
    id = payload.pop('id')
    payload.pop('builtin')
    payload['name'] = 'CANARY'

    results = PUT(f'/filesystem/acltemplate/id/{id}/', payload)
    assert results.status_code == 422, results.text


@pytest.mark.parametrize('acltype', ['NFSV4', 'POSIX'])
def test_50_delete_test1_dataset(request, acltype):
    depends(request, ["ACLTEMPLATE_DATASETS_CREATED"], scope="session")
    dataset_name = f'{pool_name}/acltemplate_{acltype.lower()}'
    results = DELETE(f'/pool/dataset/id/{dataset_name.replace("/", "%2F")}/')
    assert results.status_code == 200, results.text
