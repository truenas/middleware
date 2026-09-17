import errno
import os

import pytest

from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call

from auto_config import pool_name


def origin_of(path: str) -> str | None:
    rv = call("zfs.resource.query", {"paths": [path], "properties": ["origin"]})
    return rv[0]["properties"]["origin"]["value"]


def test_promote_clone_clears_its_origin():
    with dataset("test_promote_src") as src:
        with snapshot(src, "snap1") as snap:
            clone = os.path.join(pool_name, "test_promote_clone")
            call("zfs.resource.snapshot.clone", {"snapshot": snap, "dataset": clone})
            try:
                assert origin_of(clone) == snap

                call("zfs.resource.promote", clone)

                assert origin_of(clone) is None
                assert origin_of(src) == f"{clone}@snap1"
            finally:
                # promote `src` back so the snapshot returns to it and the
                # clone can be destroyed on its own
                call("zfs.resource.promote", src)
                call("zfs.resource.destroy", {"path": clone, "recursive": True})


def test_promote_non_clone_is_rejected():
    with dataset("test_promote_plain") as ds:
        with pytest.raises(ValidationError) as ve:
            call("zfs.resource.promote", ds)
        assert ve.value.attribute == "zfs.resource.promote"
        assert ve.value.errmsg == f"{ds!r} is not a clone and cannot be promoted"
        assert ve.value.errno == errno.EINVAL


def test_promote_nonexistent_raises_enoent():
    path = os.path.join(pool_name, "test_promote_missing")
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.promote", path)
    assert ve.value.errmsg == f"{path!r} not found"
    assert ve.value.errno == errno.ENOENT


def test_promote_empty_name_is_rejected():
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.promote", "")
    assert ve.value.attribute == "zfs.resource.promote"
    assert ve.value.errmsg == "'current_name' key is required"
