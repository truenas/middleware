from dataclasses import dataclass

import pytest

from middlewared.service_exception import ValidationError
from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset


@dataclass(frozen=True)
class QuotaConfig:
    # user quota value
    uq_value: int = 1000000
    # group quota value
    gq_value: int = uq_value * 2
    # dataset quota value
    dq_value: int = gq_value + 10000
    # dataset refquota value
    drq_value: int = dq_value + 10000
    # temp dataset name
    ds_name: str = 'temp_quota_ds_name'


@pytest.fixture(scope='module')
def temp_ds():
    with dataset(QuotaConfig.ds_name) as ds:
        yield ds


@pytest.fixture(scope='module')
def temp_user(temp_ds):
    user_info = {
        'username': 'test_quota_user',
        'full_name': 'Test Quota User',
        'password': 'test1234',
        'group_create': True,
    }
    with user(user_info) as u:
        uid = call('user.get_instance', u['id'])['uid']
        grp = call('group.query', [['group', '=', u['username']]], {'get': True})
        yield {'uid': uid, 'gid': grp['gid'], 'user': u['username'], 'group': grp['group']}


@pytest.mark.parametrize('id_', ['0', 'root'])
@pytest.mark.parametrize(
    'quota_type,error', [
        (['USER', 'user quota on uid']),
        (['USEROBJ', 'userobj quota on uid']),
        (['GROUP', 'group quota on gid']),
        (['GROUPOBJ', 'groupobj quota on gid']),
    ],
    ids=[
        'root USER quota is prohibited',
        'root USEROBJ quota is prohibited',
        'root GROUP quota is prohibited',
        'root GROUPOBJ quota is prohibited',
    ],
)
def test_error(temp_ds, id_, quota_type, error):
    """Changing any quota type for the root user/group should be prohibited"""
    with pytest.raises(ValidationError) as ve:
        call('pool.dataset.set_quota', temp_ds, [{'quota_type': quota_type, 'id': id_, 'quota_value': 5242880}])
    assert ve.value.errmsg == f'Setting {error} [0] is not permitted'


def test_quotas(temp_ds, temp_user):
    user, uid = temp_user['user'], temp_user['uid']
    group, gid = temp_user['group'], temp_user['gid']
    uq_value = QuotaConfig.uq_value
    gq_value = QuotaConfig.gq_value
    dq_value = QuotaConfig.dq_value
    drq_value = QuotaConfig.drq_value

    call('pool.dataset.set_quota', temp_ds, [
        {'quota_type': 'USER', 'id': user, 'quota_value': uq_value},
        {'quota_type': 'USEROBJ', 'id': user, 'quota_value': uq_value},
        {'quota_type': 'GROUP', 'id': group, 'quota_value': gq_value},
        {'quota_type': 'GROUPOBJ', 'id': group, 'quota_value': gq_value},
        {'quota_type': 'DATASET', 'id': 'QUOTA', 'quota_value': dq_value},
        {'quota_type': 'DATASET', 'id': 'REFQUOTA', 'quota_value': drq_value},
    ])

    verify_info = (
        (
            {
                'quota_type': 'USER',
                'id': uid,
                'quota': uq_value,
                'obj_quota': uq_value,
                'name': user
            },
            'USER',
        ),
        (
            {
                'quota_type': 'GROUP',
                'id': gid,
                'quota': gq_value,
                'obj_quota': gq_value,
                'name': group
            },
            'GROUP',
        ),
        (
            {
                'quota_type': 'DATASET',
                'id': temp_ds,
                'name': temp_ds,
                'quota': dq_value,
                'refquota': drq_value,
            },
            'DATASET',
        ),
    )
    for er, quota_type in verify_info:
        for result in filter(lambda x: x['id'] == er['id'], call('pool.dataset.get_quota', temp_ds, quota_type)):
            assert all((result[j] == er[j] for j in er)), result
