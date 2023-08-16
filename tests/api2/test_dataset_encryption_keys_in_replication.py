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
                    call('zfs.snapshot.create', {'dataset': src, 'name': 'snap-1', 'recursive': True})
                    call('replication.run', task['id'], job=True)
                    keys = call('pool.dataset.export_keys_for_replication_internal', task['id'])
                    unlocked_info = call(
                        'pool.dataset.unlock', dst, {
                            'datasets': [{'name': name, 'key': key} for name, key in keys.items()],
                        }, job=True
                    )
                    assert unlocked_info['unlocked'] == [dst], unlocked_info
