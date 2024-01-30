import pytest
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

pytestmark = pytest.mark.zfs


def test_dataset_mount_on_readonly_dataset():
    src_parent_dataset_name = 'parent_src'
    with dataset(src_parent_dataset_name) as parent_src:
        with dataset(f'{src_parent_dataset_name}/child1', {'readonly': 'ON'}) as child1_ds:
            with dataset(f'{src_parent_dataset_name}/child2', {'readonly': 'ON'}) as child2_ds:
                call('zfs.dataset.create', {'name': f'{child1_ds}/failed'})
                call('zfs.dataset.umount', parent_src, {'force': True})
                call('zfs.dataset.mount', parent_src, {'recursive': True})
                for source_dataset, mounted in (
                    (parent_src, 'yes'),
                    (child1_ds, 'yes'),
                    (f'{child1_ds}/failed', 'no'),
                    (child2_ds, 'yes'),
                ):
                    assert call('zfs.dataset.get_instance', source_dataset)['properties']['mounted']['value'] == mounted
