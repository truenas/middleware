#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os
from middlewared.test.integration.utils import call, ssh
apifolder = os.getcwd()
sys.path.append(apifolder)


def delete_group_delete_users(delete_users):
    user_id = call("user.create", {
        "username": "test",
        "group_create": True,
        "full_name": "Test",
        "smb": False,
        "password_disabled": True,
    })

    results = call(f"user.query", [["id", "=", user_id]])
    group_id = results[0]["group"]["id"]

    call("group.delete", group_id, {"delete_users": delete_users})

    return user_id, group_id


def test_01_delete_group_delete_users():
    user_id, group_id = delete_group_delete_users(True)

    results = call(f"user.query", [["id", "=", user_id]])
    assert results == []


def test_01_delete_group_no_delete_users():
    user_id, group_id = delete_group_delete_users(False)

    results = call(f"user.query", [["id", "=", user_id]])
    assert results["group"]["bsdgrp_group"] in ["nogroup", "nobody"]

    results = call("user.delete", user_id)
