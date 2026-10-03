import errno

import pytest

from middlewared.plugins.pool_.dataset import rekey_update_errors, translate_update
from middlewared.service_exception import ValidationErrors


def rekeyed(sent, *attributes):
    verrors = ValidationErrors()
    rekey_update_errors(verrors, sent, [(attribute, "wrong", errno.EINVAL) for attribute in attributes])
    return [e.attribute for e in verrors.errors]


def test_update_rekeys_zfs_errors_in_order():
    assert rekeyed(
        {"recordsize", "acltype", "managedby"},
        "zfs.resource.set.properties.recordsize",
        "zfs.resource.set.properties.aclmode",
        "zfs.resource.set.inherit.org.truenas:managedby",
    ) == [
        "pool_dataset_update.recordsize",
        "pool_dataset_update.acltype",
        "pool_dataset_update.managedby",
    ]


@pytest.mark.parametrize(
    "sent,attribute,expected",
    [
        ({"volsize"}, "zfs.resource.set.properties.refreservation", "pool_dataset_update.volsize"),
        (
            {"user_properties_update"},
            "zfs.resource.set.inherit.custom:x",
            "pool_dataset_update.user_properties_update",
        ),
        ({"user_properties_update"}, "zfs.resource.set.user_properties", "pool_dataset_update.user_properties_update"),
        ({"atime"}, "zfs.resource.set.properties", "pool_dataset_update"),
    ],
)
def test_update_rekeys_each_error_class(sent, attribute, expected):
    assert rekeyed(sent, attribute) == [expected]


def test_update_translates_values():
    assert translate_update(
        {
            "compression": "LZ4",
            "deduplication": "ON",
            "quota": None,
            "copies": 2,
            "atime": "INHERIT",
            "user_properties_update": [{"key": "a:b", "remove": True}],
        }
    ) == ({"compression": "lz4", "copies": 2, "dedup": "on", "quota": 0}, {}, ["atime", "a:b"])
