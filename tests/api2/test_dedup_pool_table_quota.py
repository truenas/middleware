import pytest

from truenas_api_client.exc import ValidationErrors

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call


def dedup_pool_payload(dedup_table_quota: str | None, dedup_table_quota_value: int | None) -> dict:
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 2:
        pytest.skip('Insufficient number of disks to perform this test')

    return {
        'deduplication': 'ON',
        'topology': {
            'data': [{
                'type': 'STRIPE',
                'disks': [unused_disks[0]['name']]
            }],
            'dedup': [{
                'type': 'STRIPE',
                'disks': [unused_disks[1]['name']]
            }],
        },
        'dedup_table_quota': dedup_table_quota,
        'dedup_table_quota_value': dedup_table_quota_value,
        'allow_duplicate_serials': True,
    }


@pytest.fixture(scope='module')
def dedup_pool():
    with another_pool(dedup_pool_payload('CUSTOM', 2048)) as pool:
        yield pool


@pytest.mark.parametrize(
    'dedup_table_quota,dedup_table_quota_value,error_msg,error_attr', [
        (
            None,
            1024,
            'You must set Deduplication Table Quota to CUSTOM to specify a value.',
            'pool_create.dedup_table_quota'
        ),
        (
            'AUTO',
            1024,
            'You must set Deduplication Table Quota to CUSTOM to specify a value.',
            'pool_create.dedup_table_quota'
        ),
        (
            'CUSTOM',
            None,
            'This field is required when Deduplication Table Quota is set to CUSTOM.',
            'pool_create.dedup_table_quota_value'
        ),
    ]
)
def test_dedup_table_quota_create_validation(dedup_table_quota, dedup_table_quota_value, error_msg, error_attr):
    with pytest.raises(ValidationErrors) as ve:
        with another_pool(dedup_pool_payload(dedup_table_quota, dedup_table_quota_value)):
            pass

    assert ve.value.errors[0].attribute == error_attr
    assert ve.value.errors[0].errmsg == error_msg


def test_dedup_table_quota_value_on_create(dedup_pool):
    assert call('pool.get_instance', dedup_pool['id'])['dedup_table_quota'] == '2048'


@pytest.mark.parametrize(
    'dedup_table_quota,dedup_table_quota_value,expected_value,error_msg,error_attr', [
        (None, None, '0', '', ''),
        (
            None,
            1024,
            '',
            'You must set Deduplication Table Quota to CUSTOM to specify a value.',
            'pool_update.dedup_table_quota'
        ),
        ('AUTO', None, 'auto', '', ''),
        (
            'AUTO',
            1024,
            '',
            'You must set Deduplication Table Quota to CUSTOM to specify a value.',
            'pool_update.dedup_table_quota'
        ),
        ('CUSTOM', 1024, '1024', '', ''),
        (
            'CUSTOM',
            None,
            '',
            'This field is required when Deduplication Table Quota is set to CUSTOM.',
            'pool_update.dedup_table_quota_value'
        ),
    ]
)
def test_dedup_table_quota_update(
    dedup_pool, dedup_table_quota, dedup_table_quota_value, expected_value, error_msg, error_attr
):
    if error_msg:
        with pytest.raises(ValidationErrors) as ve:
            call(
                'pool.update', dedup_pool['id'], {
                    'dedup_table_quota': dedup_table_quota,
                    'dedup_table_quota_value': dedup_table_quota_value,
                    'allow_duplicate_serials': True,
                }, job=True)
        assert ve.value.errors[0].attribute == error_attr
        assert ve.value.errors[0].errmsg == error_msg
    else:
        call(
            'pool.update', dedup_pool['id'], {
                'dedup_table_quota': dedup_table_quota,
                'dedup_table_quota_value': dedup_table_quota_value,
                'allow_duplicate_serials': True
            }, job=True)
        assert call('pool.get_instance', dedup_pool['id'])['dedup_table_quota'] == expected_value
