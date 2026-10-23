import errno

import pytest

from middlewared.api.current import ZFSResourceUserspaceEntry
from middlewared.plugins.pool_.dataset_quota import (
    rekey_set_quota_error,
    translate_set_quota,
    userspace_rows_to_legacy,
)
from middlewared.service_exception import ValidationError

UNRESOLVABLE = 4000000


def test_translate_merges_rows_per_id_and_keeps_the_last_value():
    plan = translate_set_quota(
        [
            {"quota_type": "USER", "id": 1000, "quota_value": 1024},
            {"quota_type": "DATASET", "id": "QUOTA", "quota_value": None},
            {"quota_type": "USEROBJ", "id": 1000, "quota_value": 0},
            {"quota_type": "GROUP", "id": 1000, "quota_value": 2048},
            {"quota_type": "USER", "id": 1000, "quota_value": 4096},
        ]
    )
    assert plan.items == [
        {"type": "user", "xid": 1000, "quota": 4096, "objquota": 0},
        {"type": "group", "xid": 1000, "quota": 2048, "objquota": None},
    ]
    assert plan.props == {"quota": 0}


@pytest.mark.parametrize(
    "attribute,xid,expected_attribute,expected_message",
    [
        (
            "zfs.resource.userspace.set.quotas.0.xid",
            0,
            "quotas.2.id",
            "Setting groupobj quota on gid [0] is not permitted",
        ),
        ("zfs.resource.userspace.set.quotas.0.xid", 5, "quotas.2.id", "msg"),
        ("zfs.resource.userspace.set.quotas.0.objquota", 5, "quotas.3.quota_value", "msg"),
        ("zfs.resource.userspace.set.quotas.0", 5, "quotas.2", "msg"),
        ("zfs.resource.userspace.set.path", 5, "dataset", "msg"),
        ("zfs.resource.set.properties.refquota", 5, "quotas.1.quota_value", "msg"),
        ("zfs.resource.set.properties", 5, "quotas", "msg"),
        ("zfs.resource.set.path", 5, "dataset", "msg"),
        ("zfs.resource.set", 5, "dataset", "msg"),
    ],
)
def test_rekey_reports_on_the_legacy_row(attribute, xid, expected_attribute, expected_message):
    plan = translate_set_quota(
        [
            {"quota_type": "DATASET", "id": "QUOTA", "quota_value": 1},
            {"quota_type": "DATASET", "id": "REFQUOTA", "quota_value": 1},
            {"quota_type": "GROUPOBJ", "id": xid, "quota_value": 1},
            {"quota_type": "GROUPOBJ", "id": xid, "quota_value": 2},
        ]
    )
    e = rekey_set_quota_error(ValidationError(attribute, "msg", errno.EINVAL), plan)
    assert (e.attribute, e.errmsg, e.errno) == (expected_attribute, expected_message, errno.EINVAL)


def test_legacy_rows_leave_out_zero_values_and_unresolved_names():
    row = ZFSResourceUserspaceEntry(
        dataset="tank/a", type="user", xid=UNRESOLVABLE, used=512, quota=0, objused=3, objquota=0
    )
    assert userspace_rows_to_legacy([row], "USER") == [
        {"quota_type": "USER", "id": UNRESOLVABLE, "name": None, "used_bytes": 512, "obj_used": 3}
    ]
