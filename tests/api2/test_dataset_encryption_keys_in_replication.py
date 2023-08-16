from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.utils import call


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
        'pool.dataset.unlock', target_dataset, {
            'datasets': [{'name': name, 'key': key} for name, key in keys.items()],
            'recursive': True,
        }, job=True
    )
    assert set(unlocked_info['unlocked']) == set(unlocked_datasets), unlocked_info


def test_single_source_replication():
    with dataset('source_test', encryption_props(), pool='tank') as src:
        with dataset('parent_destination', encryption_props(), pool='tank') as parent_ds:
            with dataset(f'{parent_ds.rsplit("/", 1)[-1]}/destination_test', pool='tank') as dst:
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
    with dataset('source_test', encryption_props(), pool='tank') as src:
        with dataset(f'{src.rsplit("/", 1)[-1]}/child_source_test', encryption_props(), pool='tank') as child_src:
            with dataset('parent_destination', encryption_props(), pool='tank') as parent_ds:
                with dataset(f'{parent_ds.rsplit("/", 1)[-1]}/destination_test', pool='tank') as dst:
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
