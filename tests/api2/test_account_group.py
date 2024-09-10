import pytest

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.utils import call


def test_delete_group_delete_users():
    with group({
        "name": "group1",
    }) as g:
        with user({
            "username": "user1",
            "full_name": "user1",
            "group": g["id"],
            "password": "test1234",
        }) as u1:
            with user({
                "username": "user2",
                "full_name": "user2",
                "group": g["id"],
                "password": "test1234",
            }) as u2:
                with user({
                    "username": "user3",
                    "full_name": "user3",
                    "group_create": True,
                    "groups": [g["id"]],
                    "password": "test1234",
                }) as u3:
                    call("group.delete", g["id"], {"delete_users": True})

                    with pytest.raises(InstanceNotFound):
                        call("user.get_instance", u1["id"])
                    with pytest.raises(InstanceNotFound):
                        call("user.get_instance", u2["id"])
                    call("user.get_instance", u3["id"])
