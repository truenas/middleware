from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool
from middlewared.test.integration.utils.audit import expect_audit_method_calls

DS_NAME = f'{pool}/audit_dataset_insert_name_here'


def test_dataset_audit():
    payload = {'name': DS_NAME}

    try:
        with expect_audit_method_calls([{
            'method': 'pool.dataset.create',
            'params': [payload | {'type': 'FILESYSTEM'}],
            'description': f'Pool dataset create {DS_NAME}',
        }]):
            call('pool.dataset.create', payload)

        with expect_audit_method_calls([{
            'method': 'pool.dataset.update',
            'params': [DS_NAME, {'atime': 'OFF'}],
            'description': f'Pool dataset update {DS_NAME}',
        }]):
            call('pool.dataset.update', DS_NAME, {'atime': 'OFF'})

    finally:
        with expect_audit_method_calls([{
            'method': 'pool.dataset.delete',
            'params': [DS_NAME],
            'description': f'Pool dataset delete {DS_NAME}',
        }]):
            call('pool.dataset.delete', DS_NAME)


def test_dataset_set_quota_audit():
    with dataset('audit_dataset_set_quota') as ds:
        quotas = [{'quota_type': 'DATASET', 'id': 'QUOTA', 'quota_value': 1048576}]
        with expect_audit_method_calls([{
            'method': 'pool.dataset.set_quota',
            'params': [ds, quotas],
            'description': f'Pool dataset set quota {ds}',
        }]):
            call('pool.dataset.set_quota', ds, quotas)
