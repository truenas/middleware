import errno

import pytest

from middlewared.service_exception import ValidationErrors, ValidationError
from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


@pytest.fixture(scope="module")
def uid_1234():
    with dataset(f"user1_homedir") as user1_homedir:
        with user({
            "username": "user1",
            "full_name": "user1",
            "group_create": True,
            "groups": [],
            "home": f"/mnt/{user1_homedir}",
            "password": "test1234",
            "uid": 1234,
        }) as uid_1234:
            yield uid_1234


@pytest.fixture(scope="module")
def gid_1234():
    with group({
        "name": "group1",
        "gid": 1234,
    }) as gid_1234:
        yield gid_1234


def test_create_duplicate_uid(uid_1234):
    with dataset(f"user2_homedir") as user2_homedir:
        with pytest.raises(ValidationErrors) as ve:
            with user({
                "username": "user2",
                "full_name": "user2",
                "group_create": True,
                "groups": [],
                "home": f"/mnt/{user2_homedir}",
                "password": "test1234",
                "uid": 1234,
            }):
                pass

        assert ve.value.errors == [
            ValidationError('user_create.uid', 'Uid 1234 is already used (user user1 has it)', errno.EEXIST),
        ]


def test_create_duplicate_gid(gid_1234):
    with pytest.raises(ValidationErrors) as ve:
        with group({
            "name": "group2",
            "gid": 1234,
        }):
            pass

    assert ve.value.errors == [
        ValidationError('group_create.gid', 'Gid 1234 is already used (group group1 has it)', errno.EEXIST),
    ]
