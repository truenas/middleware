import pytest

from middlewared.test.integration.assets.filesystem import directory
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.product import product_type
from middlewared.test.integration.utils import call, ssh, password
from middlewared.test.integration.utils.client import truenas_server
from middlewared.service_exception import ValidationErrors
from protocols import SSH_NFS

SNAPDIR_EXPORTS_ENTRY = 'zfs_snapdir'


@pytest.fixture(scope='module')
def start_nfs():
    call('service.control', 'START', 'nfs', job=True)
    yield
    call('service.control', 'STOP', 'nfs', job=True)


@pytest.fixture(scope='function')
def enterprise():
    with product_type():
        yield


@pytest.fixture(scope='module')
def nfs_dataset():
    with dataset('nfs_snapdir') as ds:
        ssh(f'echo -n Cats > /mnt/{ds}/canary')
        call('pool.snapshot.create', {'dataset': ds, 'name': 'now'})
        yield ds


@pytest.fixture(scope='function')
def community():
    with product_type('COMMUNITY_EDITION'):
        yield


@pytest.fixture(scope='function')
def nfs_export(nfs_dataset):
    share = call('sharing.nfs.create', {'path': f'/mnt/{nfs_dataset}'})
    try:
        yield share['id']
    finally:
        call('sharing.nfs.delete', share['id'])


def test__snapdir_community_fail_create(community, nfs_dataset):
    with pytest.raises(ValidationErrors, match='This is an enterprise feature'):
        share = call('sharing.nfs.create', {
            'path': f'/mnt/{nfs_dataset}',
            'expose_snapshots': True
        })
        # cleanup just in case test failed
        call('sharing.nfs.delete', share['id'])


def test__snapdir_community_fail_update(community, nfs_export):
    with pytest.raises(ValidationErrors, match='This is an enterprise feature'):
        call('sharing.nfs.update', nfs_export, {'expose_snapshots': True})


def test__snapdir_enterprise_fail_subdir(enterprise, nfs_dataset):
    with directory(f'/mnt/{nfs_dataset}/subdir') as d:
        with pytest.raises(ValidationErrors, match='not the root directory of a dataset'):
            share = call('sharing.nfs.create', {
                'path': d,
                'expose_snapshots': True
            })
            # cleanup just in case test failed
            call('sharing.nfs.delete', share['id'])


def test__snapdir_enable_enterprise_create(start_nfs, enterprise, nfs_dataset):
    """ check that create sets correct exports line """
    share = call('sharing.nfs.create', {
        'path': f'/mnt/{nfs_dataset}',
        'expose_snapshots': True
    })

    try:
        assert share['expose_snapshots'] is True
        exports = ssh('cat /etc/exports')
        assert SNAPDIR_EXPORTS_ENTRY in exports
    finally:
        call('sharing.nfs.delete', share['id'])


def test__snapdir_enable_enterprise_update(start_nfs, enterprise, nfs_export):
    """ check that update sets correct exports line """
    exports = ssh('cat /etc/exports')
    assert SNAPDIR_EXPORTS_ENTRY not in exports

    share = call('sharing.nfs.update', nfs_export, {'expose_snapshots': True})
    assert share['expose_snapshots'] is True

    exports = ssh('cat /etc/exports')
    assert SNAPDIR_EXPORTS_ENTRY in exports

    share = call('sharing.nfs.update', nfs_export, {'expose_snapshots': False})
    assert share['expose_snapshots'] is False

    exports = ssh('cat /etc/exports')
    assert SNAPDIR_EXPORTS_ENTRY not in exports


@pytest.mark.parametrize('vers', [3, 4])
def test__snapdir_functional(start_nfs, enterprise, nfs_dataset, nfs_export, vers):
    share = call('sharing.nfs.update', nfs_export, {'expose_snapshots': True})
    assert share['expose_snapshots'] is True
    call('service.control', 'STOP', 'nfs', job=True)
    call('service.control', 'START', 'nfs', {'silent': False}, job=True)
    with SSH_NFS(
        hostname=truenas_server.ip,
        path=f'/mnt/{nfs_dataset}',
        vers=vers,
        user='root',
        password=password(),
        ip=truenas_server.ip
    ) as n:

        contents = n.ls('.')
        assert 'canary' in contents

        snapdir_contents = n.ls('.zfs/snapshot/now')
        assert 'canary' in snapdir_contents
