import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_log, expect_audit_method_calls


def test_pool_update_audit_success():
    with another_pool() as pool:
        params = [pool['id'], {'autotrim': 'ON'}]
        with expect_audit_log([{
            'event_data': {
                'authenticated': True,
                'authorized': True,
                'method': 'pool.update',
                'params': params,
                'description': f'Pool update test',
            },
            'success': True,
        }]):
            call('pool.update', *params, job=True)


def test_pool_update_audit_error():
    with another_pool() as pool:
        params = [pool['id'], {'topology': {'spares': ['nonexistent']}}]

        with expect_audit_log([{
            'event_data': {
                'authenticated': True,
                'authorized': True,
                'method': 'pool.update',
                'params': params,
                'description': f'Pool update test',
            },
            'success': False,
        }]):
            with pytest.raises(Exception):
                call('pool.update', *params, job=True)


def test_pool_create_and_export_audit():
    unused_disks = call('disk.get_unused')
    assert len(unused_disks) >= 1

    pool_name = 'TempPool'
    create_payload =  {
        'name': pool_name,
        'topology': {'data': [{'type': 'STRIPE', 'disks': [unused_disks[0]['name']]}]}
    }

    with expect_audit_method_calls([{
        'method': 'pool.create',
        'params': [create_payload],
        'description': f'Pool create {pool_name}',
    }]):
        pool_id = call('pool.create', create_payload, job=True)['id']

    export_payload = {'destroy': True}

    with expect_audit_method_calls([{
        'method': 'pool.export',
        'params': [pool_id, export_payload],
        'description': f'Pool Export {pool_name}',
    }]):
        call('pool.export', pool_id, export_payload, job=True)
