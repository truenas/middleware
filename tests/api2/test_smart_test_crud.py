import contextlib
import re

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call

pytestmark = pytest.mark.disk


@contextlib.contextmanager
def smart_test(data):
    test = call("smart.test.create", data)
    try:
        yield test
    finally:
        call("smart.test.delete", test["id"])


def smart_test_disks(all_disks=False, disk_index=0):
    if all_disks:
        return {"all_disks": True}
    else:
        return {"disks": [sorted(call("smart.test.disk_choices").keys())[disk_index]]}


@pytest.mark.parametrize("existing_all_disks", [False, True])
@pytest.mark.parametrize("new_all_disks", [False, True])
def test_smart_test_already_has_tests_for_this_type(existing_all_disks, new_all_disks):
    if existing_all_disks:
        error = "There already is an all-disks SHORT test"
    else:
        error = "The following disks already have SHORT test: sd[a-z]"

    with smart_test({
        "schedule": {
            "hour": "0",
            "dom": "*",
            "month": "*",
            "dow": "*",
        },
        **smart_test_disks(existing_all_disks),
        "type": "SHORT",
    }):
        with pytest.raises(ValidationErrors) as ve:
            with smart_test({
                "schedule": {
                    "hour": "1",
                    "dom": "*",
                    "month": "*",
                    "dow": "*",
                },
                **smart_test_disks(new_all_disks),
                "type": "SHORT",
            }):
                pass

        assert re.fullmatch(error, ve.value.errors[0].errmsg)


@pytest.mark.parametrize("existing_all_disks", [False, True])
@pytest.mark.parametrize("new_all_disks", [False, True])
def test_smart_test_intersect(existing_all_disks, new_all_disks):
    with smart_test({
        "schedule": {
            "hour": "3",
            "dom": "1",
            "month": "*",
            "dow": "*",
        },
        **smart_test_disks(existing_all_disks),
        "type": "LONG",
    }):
        with pytest.raises(ValidationErrors) as ve:
            with smart_test({
                "schedule": {
                    "hour": "3",
                    "dom": "*",
                    "month": "*",
                    "dow": "1",
                },
                **smart_test_disks(existing_all_disks),
                "type": "SHORT",
            }):
                pass

        assert ve.value.errors[0].errmsg == "A LONG test already runs at Day 1st of every month, Mon, 03:00"


def test_smart_test_update():
    with smart_test({
        "schedule": {
            "hour": "0",
            "dom": "*",
            "month": "*",
            "dow": "*",
        },
        **smart_test_disks(True),
        "type": "SHORT",
    }) as test:
        call("smart.test.update", test["id"], {})
