import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_log


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
