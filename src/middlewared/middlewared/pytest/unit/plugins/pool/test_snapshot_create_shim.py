import errno
from unittest.mock import Mock

import pytest

from middlewared.api.current import (
    ZFSResourceSnapshotCreateQuery,
    ZFSResourceSnapshotEntry,
    ZFSResourceSnapshotPropertiesEntry,
)
from middlewared.api.v27_0_0.zfs_resource_crud import PropertyValue
from middlewared.plugins.pool_.snapshot import PoolSnapshotService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import ValidationError


def make_service(public_create):
    middleware = Middleware()
    middleware.services.zfs.resource.snapshot.create = public_create
    return middleware, PoolSnapshotService(middleware)


def test_create_returns_entry_from_public_model():
    public_create = Mock(
        return_value=ZFSResourceSnapshotEntry(
            createtxg=123,
            guid=1,
            name="tank/ds@snap",
            pool="tank",
            dataset="tank/ds",
            snapshot_name="snap",
            holds=None,
            user_properties=None,
            properties=ZFSResourceSnapshotPropertiesEntry(
                creation=PropertyValue(raw="1700000000", source=None, value=1700000000),
                createtxg=PropertyValue(raw="123", source=None, value=123),
            ),
        )
    )
    middleware, svc = make_service(public_create)

    entry = svc.do_create({"dataset": "tank/ds", "name": "snap"})

    assert entry == {
        "id": "tank/ds@snap",
        "name": "tank/ds@snap",
        "pool": "tank",
        "type": "SNAPSHOT",
        "snapshot_name": "snap",
        "dataset": "tank/ds",
        "createtxg": "123",
        "properties": {
            "creation": {"value": "1700000000", "rawvalue": "1700000000", "source": "NONE", "parsed": 1700000000},
            "createtxg": {"value": "123", "rawvalue": "123", "source": "NONE", "parsed": 123},
        },
    }

    public_create.assert_called_once()
    (query,) = public_create.call_args.args
    assert isinstance(query, ZFSResourceSnapshotCreateQuery)
    assert (query.dataset, query.name, query.recursive, query.exclude, query.user_properties) == (
        "tank/ds",
        "snap",
        False,
        [],
        {},
    )

    middleware.send_event.assert_called_once()
    assert middleware.send_event.call_args.args == ("pool.snapshot.query", "ADDED")


@pytest.mark.parametrize(
    "source_attribute,expected_attribute,errnum",
    [
        ("zfs.resource.snapshot.create", "pool.snapshot.create", errno.ENOENT),
        ("zfs.resource.snapshot.create", "pool.snapshot.create", errno.EEXIST),
        ("zfs.resource.snapshot.create.exclude", "pool.snapshot.create.exclude", errno.EINVAL),
    ],
)
def test_create_rekeys_public_validation_errors(source_attribute, expected_attribute, errnum):
    _, svc = make_service(Mock(side_effect=ValidationError(source_attribute, "msg", errnum)))

    with pytest.raises(ValidationError) as ve:
        svc.do_create({"dataset": "tank/ds", "name": "snap"})

    assert (ve.value.attribute, ve.value.errmsg, ve.value.errno) == (expected_attribute, "msg", errnum)


def test_create_passes_through_unrelated_validation_errors():
    _, svc = make_service(
        Mock(side_effect=ValidationError("pool_dataset_update.user_properties_update", "x", errno.EINVAL))
    )

    with pytest.raises(ValidationError) as ve:
        svc.do_create({"dataset": "tank/ds", "name": "snap"})

    assert (ve.value.attribute, ve.value.errmsg, ve.value.errno) == (
        "pool_dataset_update.user_properties_update",
        "x",
        errno.EINVAL,
    )
