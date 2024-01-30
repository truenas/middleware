import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.utils import call


pytestmark = pytest.mark.zfs
BASE_REPLICATION = {
    'direction': 'PUSH',
    'transport': 'LOCAL',
    'source_datasets': [],
    'target_dataset': None,
    'recursive': False,
    'auto': False,
    'retention_policy': 'NONE',
}


def encryption_props():
    return {
        'encryption_options': {'generate_key': True},
        'encryption': True,
        'inherit_encryption': False
    }


def make_assertions(source_datasets, task_id, target_dataset, unlocked_datasets):
    for source_ds in source_datasets:
        call('zfs.snapshot.create', {'dataset': source_ds, 'name': 'snaptest-1', 'recursive': True})

    call('replication.run', task_id, job=True)
    keys = call('pool.dataset.export_keys_for_replication_internal', task_id)
    unlocked_info = call(
        'pool.dataset.unlock', target_dataset.split('/', 1)[0], {
            'datasets': [{'name': name, 'key': key} for name, key in keys.items()],
            'recursive': True,
        }, job=True
    )
    assert set(unlocked_info['unlocked']) == set(unlocked_datasets), unlocked_info


def test_single_source_replication():
    with dataset('source_test', encryption_props()) as src:
        with dataset('parent_destination', encryption_props()) as parent_ds:
            with dataset(f'{parent_ds.rsplit("/", 1)[-1]}/destination_test') as dst:
                with replication_task({
                    **BASE_REPLICATION,
                    'name': 'encryption_replication_test',
                    'source_datasets': [src],
                    'target_dataset': dst,
                    'name_regex': '.+',
                    'auto': False,
                }) as task:
                    make_assertions([src], task['id'], dst, [dst])


def test_single_source_recursive_replication():
    with dataset('source_test', encryption_props()) as src:
        with dataset(f'{src.rsplit("/", 1)[-1]}/child_source_test', encryption_props()) as child_src:
            with dataset('parent_destination', encryption_props()) as parent_ds:
                with dataset(f'{parent_ds.rsplit("/", 1)[-1]}/destination_test') as dst:
                    with replication_task({
                        **BASE_REPLICATION,
                        'name': 'encryption_replication_test',
                        'source_datasets': [src],
                        'target_dataset': dst,
                        'name_regex': '.+',
                        'auto': False,
                        'recursive': True,
                    }) as task:
                        make_assertions([src], task['id'], dst, [dst, f'{dst}/{child_src.rsplit("/", 1)[-1]}'])


def test_single_source_child_encrypted_replication():
    with dataset('source_test', encryption_props()) as src:
        with dataset(f'{src.rsplit("/", 1)[-1]}/child_source_test', encryption_props()) as child_src:
            with dataset('parent_destination', encryption_props()) as parent_ds:
                with dataset(f'{parent_ds.rsplit("/", 1)[-1]}/destination_test') as dst:
                    with replication_task({
                        **BASE_REPLICATION,
                        'name': 'encryption_replication_test',
                        'source_datasets': [child_src],
                        'target_dataset': dst,
                        'name_regex': '.+',
                        'auto': False,
                        'recursive': True,
                    }) as task:
                        make_assertions([child_src], task['id'], dst, [dst])


def test_multiple_source_replication():
    with dataset('source_test1', encryption_props()) as src1:
        with dataset('source_test2', encryption_props()) as src2:
            with dataset('parent_destination', encryption_props()) as parent_ds:
                with dataset(f'{parent_ds.rsplit("/", 1)[-1]}/destination_test') as dst:
                    with replication_task({
                        **BASE_REPLICATION,
                        'name': 'encryption_replication_test',
                        'source_datasets': [src1, src2],
                        'target_dataset': dst,
                        'name_regex': '.+',
                        'auto': False,
                    }) as task:
                        make_assertions(
                            [src1, src2], task['id'], dst, [f'{dst}/{k.rsplit("/", 1)[-1]}' for k in [src1, src2]]
                        )


def test_multiple_source_recursive_replication():
    with dataset('source_test1', encryption_props()) as src1:
        with dataset(f'{src1.rsplit("/", 1)[-1]}/child_source_test1', encryption_props()) as child_src1:
            with dataset('source_test2', encryption_props()) as src2:
                with dataset(f'{src2.rsplit("/", 1)[-1]}/child_source_test2', encryption_props()) as child_src2:
                    with dataset('parent_destination', encryption_props()) as parent_ds:
                        with dataset(f'{parent_ds.rsplit("/", 1)[-1]}/destination_test') as dst:
                            with replication_task({
                                **BASE_REPLICATION,
                                'name': 'encryption_replication_test',
                                'source_datasets': [src1, src2],
                                'target_dataset': dst,
                                'name_regex': '.+',
                                'auto': False,
                                'recursive': True,
                            }) as task:
                                make_assertions(
                                    [src1, src2], task['id'], dst, [
                                        f'{dst}/{"/".join(k.rsplit("/")[-abs(n):])}' for k, n in [
                                            (src1, 1), (src2, 1), (child_src1, 2), (child_src2, 2),
                                        ]
                                    ]
                                )


@pytest.mark.parametrize('keys_available_for_download', [False, True])
def test_replication_task_reports_keys_available_for_download(keys_available_for_download):
    with dataset('source_test', encryption_props() if keys_available_for_download else {}) as src:
        with dataset('parent_destination', encryption_props() if keys_available_for_download else {}) as parent_ds:
            with dataset(f'{parent_ds.rsplit("/", 1)[-1]}/destination_test') as dst:
                with replication_task({
                    **BASE_REPLICATION,
                    'name': 'encryption_replication_test',
                    'source_datasets': [src],
                    'target_dataset': dst,
                    'name_regex': '.+',
                    'auto': False,
                }) as task:
                    task = call(
                        'replication.get_instance', task['id'], {'extra': {'check_dataset_encryption_keys': True}}
                    )
                    assert task['has_encrypted_dataset_keys'] is keys_available_for_download, task

