import contextlib
import os
import pytest

from pathlib import Path
from pytest_dependency import depends

from middlewared.client.client import ValidationErrors
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.assets.apps import chart_release
from middlewared.test.integration.assets.catalog import catalog

USER_ID = 568
TEST_DIR = 'test_dir_for_acl'
pytestmark = pytest.mark.apps


def path_exists(path: str) -> bool:
    with contextlib.suppress(Exception):
        return call('filesystem.stat', path) is not None
    return False


def path_is_dir(path: str) -> bool:
    with contextlib.suppress(Exception):
        return call('filesystem.stat', path)['type'] == 'DIRECTORY'
    return False


@contextlib.contextmanager
def hostpath_dir(path: str, non_empty: bool = False):
    if not path_exists(path):
        call('filesystem.mkdir', path)
    if non_empty:
        ssh(f'touch {path}/test1')

    try:
        yield path
    finally:
        ssh(f'rm -rf {path}')


def test_01_ix_volumes_normalization(request):
    depends(request, ['setup_kubernetes'], scope='session')
    with catalog({
        'force': True,
        'preferred_trains': ['tests'],
        'label': 'ACLTEST',
        'repository': 'https://github.com/truenas/charts.git',
        'branch': 'acl-tests'
    }) as catalog_obj:
        with chart_release({
            'catalog': catalog_obj['label'],
            'item': 'syncthing',
            'release_name': 'syncthing',
            'train': 'tests',
            'values': {'appVolumeMounts': {'config': {'hostPathEnabled': False}}},
        }) as chart_release_obj:
            for path in chart_release_obj['config']['ixVolumes']:
                assert path_exists(path['hostPath']) is True
                assert path_is_dir(path['hostPath']) is True


def test_02_acl_normalization_with_ix_volumes(request):
    depends(request, ['setup_kubernetes'], scope='session')

    with catalog({
        'force': True,
        'preferred_trains': ['tests'],
        'label': 'ACLTEST',
        'repository': 'https://github.com/truenas/charts.git',
        'branch': 'acl-tests'
    }) as catalog_obj:
        with chart_release({
            'catalog': catalog_obj['label'],
            'item': 'syncthing-with-acl',
            'release_name': 'syncthing-with-acl',
            'train': 'tests',
            'values': {
                'appVolumeMounts': {
                    'config': {
                        'testDataset': {
                            'datasetName': 'ix-syncthing_test',
                            'aclEntries': {'entries': [{'id_type': 'USER', 'id': USER_ID, 'access': 'READ'}]}
                        },
                        'hostPathEnabled': False,
                    }
                }
            }
        }) as chart_release_obj:
            for path in chart_release_obj['config']['ixVolumes']:
                assert path_exists(path['hostPath']) is True
                assert path_is_dir(path['hostPath']) is True
                assert any(
                    acl['id'] == USER_ID and acl['perms']['READ'] for acl in call(
                        'filesystem.getacl', path['hostPath']
                    )['acl']
                ) is path['hostPath'].endswith('syncthing_test')


def test_03_acl_normalization(request):
    depends(request, ['setup_kubernetes'], scope='session')

    k8s_pool = call('kubernetes.config')['pool']
    with hostpath_dir(os.path.join('/mnt', k8s_pool, 'acl-test-dir-hostpath')) as tmp_dir:
        with catalog({
            'force': True,
            'preferred_trains': ['tests'],
            'label': 'ACLTEST',
            'repository': 'https://github.com/truenas/charts.git',
            'branch': 'acl-tests'
        }) as catalog_obj:
            with chart_release({
                'catalog': catalog_obj['label'],
                'item': 'syncthing-with-acl',
                'release_name': 'syncthing-with-acl-host',
                'train': 'tests',
                'values': {
                    'aclEntries': [{
                        'path': tmp_dir,
                        'entries': [{'id_type': 'USER', 'id': USER_ID, 'access': 'READ'}]
                    }],
                }
            }):
                assert any(
                    acl['id'] == USER_ID and acl['perms']['READ'] for acl in call('filesystem.getacl', tmp_dir)['acl']
                ) is True


def test_04_acl_entries_force_flag_disabled_non_empty_path(request):
    depends(request, ['setup_kubernetes'], scope='session')

    k8s_pool = call('kubernetes.config')['pool']
    with hostpath_dir(os.path.join('/mnt', k8s_pool, 'acl-test-dir'), True) as tmp_dir:
        with catalog({
            'force': True,
            'preferred_trains': ['tests'],
            'label': 'ACLTEST',
            'repository': 'https://github.com/truenas/charts.git',
            'branch': 'acl-tests'
        }) as catalog_obj:
            with pytest.raises(ValidationErrors) as ei:
                with chart_release({
                    'catalog': catalog_obj['label'],
                    'item': 'syncthing-with-acl',
                    'release_name': 'syncthing-acl-force-enabled',
                    'train': 'tests',
                    'values': {
                        'aclEntries': [{
                            'path': tmp_dir,
                            'entries': [{'id_type': 'USER', 'id': USER_ID, 'access': 'READ'}],
                            'options': {'force': False}
                        }],
                    }
                }):
                    assert ei.value.errors[0].errmsg == (
                        f'{tmp_dir}: path contains existing data and `force` was not specified'
                    )


def test_05_acl_entries_force_flag_enabled_non_empty_path(request):
    depends(request, ['setup_kubernetes'], scope='session')

    k8s_pool = call('kubernetes.config')['pool']
    with hostpath_dir(os.path.join('/mnt', k8s_pool, 'acl-test-dir'), True) as tmp_dir:
        with catalog({
            'force': True,
            'preferred_trains': ['tests'],
            'label': 'ACLTEST',
            'repository': 'https://github.com/truenas/charts.git',
            'branch': 'acl-tests'
        }) as catalog_obj:
            with chart_release({
                'catalog': catalog_obj['label'],
                'item': 'syncthing-with-acl',
                'release_name': 'syncthing-acl-force-enabled',
                'train': 'tests',
                'values': {
                    'aclEntries': [{
                        'path': tmp_dir,
                        'entries': [{'id_type': 'USER', 'id': USER_ID, 'access': 'READ'}],
                        'options': {'force': True}
                    }],
                }
            }):
                assert any(
                    acl['id'] == USER_ID and acl['perms']['READ'] for acl in call('filesystem.getacl', tmp_dir)['acl']
                ) is True


def test_06_acl_entries_path_not_found_validation(request):
    depends(request, ['setup_kubernetes'], scope='session')
    tmp_dir = '/tmp/test_file'
    with catalog({
        'force': True,
        'preferred_trains': ['tests'],
        'label': 'ACLTEST',
        'repository': 'https://github.com/truenas/charts.git',
        'branch': 'acl-tests'
    }) as catalog_obj:
        with pytest.raises(ValidationErrors) as ei:
            with chart_release({
                'catalog': catalog_obj['label'],
                'item': 'syncthing-with-acl',
                'release_name': 'syncthing-acl-force-enabled',
                'train': 'tests',
                'values': {
                    'aclEntries': [{
                        'path': tmp_dir,
                        'entries': [{'id_type': 'USER', 'id': USER_ID, 'access': 'READ'}],
                        'options': {'force': False}
                    }],
                }
            }):
                assert ei.value.errors[0].errmsg == f'{tmp_dir}: path does not exist'
