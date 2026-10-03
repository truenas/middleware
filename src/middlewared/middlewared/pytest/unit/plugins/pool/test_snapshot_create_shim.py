import errno

from middlewared.plugins.pool_.snapshot import rekey_validation_error
from middlewared.service_exception import ValidationError


def test_rekey_keeps_the_attribute_suffix():
    e = rekey_validation_error(
        ValidationError("zfs.resource.snapshot.create.exclude", "msg", errno.EINVAL),
        "zfs.resource.snapshot.create",
        "pool.snapshot.create",
    )
    assert (e.attribute, e.errmsg, e.errno) == ("pool.snapshot.create.exclude", "msg", errno.EINVAL)


def test_rekey_returns_a_foreign_attribute_unchanged():
    e = ValidationError("pool_dataset_update.user_properties_update", "x", errno.EINVAL)
    assert rekey_validation_error(e, "zfs.resource.snapshot.create", "pool.snapshot.create") is e
