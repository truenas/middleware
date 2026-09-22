import errno
import os

import pytest

from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call

from auto_config import pool_name


def origin_of(path: str) -> str | None:
    rv = call("zfs.resource.list", {"paths": [path], "properties": ["origin"]})
    return rv[0]["properties"]["origin"]["value"]


def test_promote_clone_clears_its_origin():
    with dataset("test_promote_src") as src:
        with snapshot(src, "snap1") as snap:
            clone = os.path.join(pool_name, "test_promote_clone")
            call("zfs.resource.snapshot.clone", {"snapshot": snap, "dataset": clone})
            try:
                assert origin_of(clone) == snap

                call("zfs.resource.promote", {"path": clone})

                assert origin_of(clone) is None
                assert origin_of(src) == f"{clone}@snap1"
            finally:
                # promote `src` back so the snapshot returns to it and the
                # clone can be destroyed on its own
                call("zfs.resource.promote", {"path": src})
                call("zfs.resource.destroy", {"path": clone, "recursive": True})


def test_promote_non_clone_is_rejected():
    with dataset("test_promote_plain") as ds:
        with pytest.raises(ValidationError) as ve:
            call("zfs.resource.promote", {"path": ds})
        assert ve.value.attribute == "zfs.resource.promote"
        assert ve.value.errmsg == f"{ds!r} is not a clone and cannot be promoted"
        assert ve.value.errno == errno.EINVAL


def test_promote_nonexistent_raises_enoent():
    path = os.path.join(pool_name, "test_promote_missing")
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.promote", {"path": path})
    assert ve.value.errmsg == f"{path!r} not found"
    assert ve.value.errno == errno.ENOENT


def test_promote_empty_path_is_rejected():
    with pytest.raises(ValidationErrors) as ve:
        call("zfs.resource.promote", {"path": ""})
    assert ve.value.errors[0].attribute == "data.path"
    assert "Please provide a valid dataset name according to ZFS standards" in ve.value.errors[0].errmsg


def test_promote_protected_path_is_rejected():
    path = os.path.join(pool_name, ".system", "test_promote_protected")
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.promote", {"path": path})
    assert ve.value.attribute == "zfs.resource.promote"
    assert ve.value.errmsg == f"{path!r} is a protected path."
    assert ve.value.errno == errno.EACCES


def test_promote_bypass_is_not_settable():
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.promote", {"path": os.path.join(pool_name, ".system"), "bypass": True})

    error = str(exc_info.value)
    assert "bypass" in error, error
    assert "Extra inputs are not permitted" in error, error
