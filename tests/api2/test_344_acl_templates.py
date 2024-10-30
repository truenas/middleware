#!/usr/bin/env python3

import os
import pytest
from contextlib import contextmanager
from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.pool import dataset as make_dataset


@pytest.fixture(scope='module')
def acltemplate_ds():
    """
    Setup of datasets for testing templates.
    This test shouldn't fail unless pool.dataset endpoint is
    thoroughly broken.
    """
    with make_dataset('acltemplate_posix', data={
        'acltype': 'POSIX',
        'aclmode': 'DISCARD'
    }) as posix_ds:
        with make_dataset('acltemplate_nfsv4', data={
            'acltype': 'NFSV4',
            'aclmode': 'PASSTHROUGH'
        }) as nfsv4_ds:
            yield {'POSIX': posix_ds, 'NFSV4': nfsv4_ds}


@contextmanager
def create_entry_type(acltype):
    entry = call('filesystem.acltemplate.query', [['name', '=', f'{acltype}_RESTRICTED']], {'get': True})
    acl = entry['acl']

    payload = {
        'name': f'{acltype}_TEST',
        'acl': acl,
        'acltype': entry['acltype']
    }

    template = call('filesystem.acltemplate.create', payload)

    try:
        yield template
    finally:
        call('filesystem.acltemplate.delete', template['id'])

    # Verify actually deleted
    assert call('filesystem.acltemplate.query', [['name', '=', f'{acltype}_TEST']]) == []


@pytest.fixture(scope='function')
def tmp_posix_entry():
    with create_entry_type('POSIX') as entry:
        yield entry


@pytest.fixture(scope='function')
def tmp_nfs_entry():
    with create_entry_type('NFS4') as entry:
        yield entry


@pytest.fixture(scope='function')
def tmp_acltemplates(tmp_posix_entry, tmp_nfs_entry):
    yield {'POSIX': tmp_posix_entry, 'NFSV4': tmp_nfs_entry}


def dataset_path(data, acltype):
    return os.path.join('/mnt', data[acltype])


@pytest.mark.parametrize('acltype', ['NFSV4', 'POSIX'])
def test_check_builtin_types_by_path(acltemplate_ds, acltype):
    """
    This test verifies that we can query builtins by paths, and
    that the acltype of the builtins matches that of the
    underlying path.
    """
    expected_acltype = 'POSIX1E' if acltype == 'POSIX' else 'NFS4'
    payload = {'path': dataset_path(acltemplate_ds, acltype)}
    for entry in call('filesystem.acltemplate.by_path', payload):
        assert entry['builtin'], str(entry)
        assert entry['acltype'] == expected_acltype, str(entry)

    payload['format-options'] = {'resolve_names': True, 'ensure_builtins': True}
    for entry in call('filesystem.acltemplate.by_path', payload):
        for ace in entry['acl']:
            if ace['tag'] not in ('USER_OBJ', 'GROUP_OBJ', 'USER', 'GROUP'):
                continue

            assert ace.get('who') is not None, str(ace)


@pytest.mark.parametrize('acltype', ['NFSV4', 'POSIX'])
def test_update_new_template(tmp_acltemplates, acltype):
    """
    Rename the template we created to validated that `update`
    method works.
    """
    # shallow copy is sufficient since we're not changing nested values
    payload = tmp_acltemplates[acltype].copy()

    template_id = payload.pop('id')
    payload.pop('builtin')
    orig_name = payload.pop('name')

    payload['name'] = f'{orig_name}2'

    result = call('filesystem.acltemplate.update', template_id, payload)
    assert result['name'] == payload['name']


def test_knownfail_builtin_delete(request):
    builtin_templ = call('filesystem.acltemplate.query', [['builtin', '=', True]], {'get': True})

    with pytest.raises(Exception):
        call('filesystem.acltemplate.delete', builtin_templ['id'])


def test_knownfail_builtin_update(request):
    payload = call('filesystem.acltemplate.query', [['builtin', '=', True]], {'get': True})

    tmpl_id = payload.pop('id')
    payload.pop('builtin')
    payload['name'] = 'CANARY'

    with pytest.raises(Exception):
        call('filesystem.acltemplate.update', tmpl_id, payload)
