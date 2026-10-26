import errno

import pytest

from middlewared.api.current import ZFSResourceUserspaceEntry
from middlewared.plugins.pool_.dataset_quota import (
    UserspaceItem,
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
        UserspaceItem("user", 1000, 0, {"quota": (4096, 4), "objquota": (0, 2)}),
        UserspaceItem("group", 1000, 3, {"quota": (2048, 3)}),
    ]
    assert plan.items[1].payload() == {"type": "group", "xid": 1000, "quota": 2048}
    assert plan.props == {"quota": (0, 1)}


@pytest.mark.parametrize(
    "attribute,expected_attribute",
    [
        ("zfs.resource.userspace.set.quotas.0.xid", "quotas.2.id"),
        ("zfs.resource.userspace.set.quotas.0.objquota", "quotas.3.quota_value"),
        ("zfs.resource.userspace.set.quotas", "quotas"),
        ("zfs.resource.userspace.set.path", "dataset"),
        ("zfs.resource.set.properties.refquota", "quotas.1.quota_value"),
        ("zfs.resource.set.properties", "quotas"),
        ("zfs.resource.set.path", "dataset"),
        ("zfs.resource.set", "dataset"),
    ],
)
def test_rekey_reports_on_the_legacy_row(attribute, expected_attribute):
    plan = translate_set_quota(
        [
            {"quota_type": "DATASET", "id": "QUOTA", "quota_value": 1},
            {"quota_type": "DATASET", "id": "REFQUOTA", "quota_value": 1},
            {"quota_type": "GROUPOBJ", "id": 5, "quota_value": 1},
            {"quota_type": "GROUPOBJ", "id": 5, "quota_value": 2},
        ]
    )
    e = rekey_set_quota_error(ValidationError(attribute, "msg", errno.EINVAL), plan)
    assert (e.attribute, e.errmsg, e.errno) == (expected_attribute, "msg", errno.EINVAL)


def test_legacy_rows_leave_out_zero_values_and_unresolved_names():
    row = ZFSResourceUserspaceEntry(
        dataset="tank/a", type="user", xid=UNRESOLVABLE, used=512, quota=0, objused=3, objquota=0
    )
    assert userspace_rows_to_legacy([row], "USER") == [
        {"quota_type": "USER", "id": UNRESOLVABLE, "name": None, "used_bytes": 512, "obj_used": 3}
    ]
