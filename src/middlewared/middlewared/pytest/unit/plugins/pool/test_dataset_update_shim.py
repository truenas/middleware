import errno
from unittest.mock import Mock

import pytest

from middlewared.plugins.pool_.dataset import PoolDatasetService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import ValidationError, ValidationErrors

GiB = 1024**3

pytestmark = pytest.mark.asyncio


def make_service(set_side_effect=None, dataset_type="FILESYSTEM"):
    row = {"id": "tank/ds", "name": "tank/ds", "type": dataset_type, "user_properties": {}}
    middleware = Middleware()
    middleware["pool.dataset.query"] = lambda filters, options=None: [row]
    middleware.services.zfs.resource.set = Mock(side_effect=set_side_effect)
    return middleware, PoolDatasetService(middleware)


def zfs_errors(*attributes):
    verrors = ValidationErrors()
    for attribute in attributes:
        verrors.add(attribute, f"{attribute} is wrong", errno.EINVAL)
    return verrors


async def update(svc, data):
    return await svc.do_update(Mock(), "tank/ds", data)


@pytest.mark.parametrize(
    "dataset_type,data,expected",
    [
        (
            "FILESYSTEM",
            {"compression": "LZ4", "deduplication": "ON", "copies": 2, "sync": "ALWAYS", "quota": None},
            {"compression": "lz4", "dedup": "on", "copies": 2, "sync": "always", "quota": 0},
        ),
        ("VOLUME", {"volsize": 2 * GiB, "snapdev": "VISIBLE"}, {"volsize": 2 * GiB, "snapdev": "visible"}),
    ],
)
async def test_update_translates_to_lowercase_index_values_and_integer_sizes(dataset_type, data, expected):
    middleware, svc = make_service(dataset_type=dataset_type)

    await update(svc, data)

    (args,) = middleware.services.zfs.resource.set.call_args.args
    assert (args.path, args.dry_run) == ("tank/ds", False)
    assert args.properties.model_dump(exclude_none=True) == expected


async def test_update_rekeys_zfs_errors_in_order():
    _, svc = make_service(
        zfs_errors(
            "zfs.resource.set.properties.recordsize",
            "zfs.resource.set.properties.aclmode",
            "zfs.resource.set.inherit.org.truenas:managedby",
        )
    )

    with pytest.raises(ValidationErrors) as ve:
        await update(svc, {"recordsize": "128K", "acltype": "POSIX", "managedby": "INHERIT"})

    assert [(e.attribute, e.errmsg, e.errno) for e in ve.value.errors] == [
        ("pool_dataset_update.recordsize", "zfs.resource.set.properties.recordsize is wrong", errno.EINVAL),
        ("pool_dataset_update.acltype", "zfs.resource.set.properties.aclmode is wrong", errno.EINVAL),
        ("pool_dataset_update.managedby", "zfs.resource.set.inherit.org.truenas:managedby is wrong", errno.EINVAL),
    ]


@pytest.mark.parametrize(
    "dataset_type,data,error,expected",
    [
        ("VOLUME", {"volsize": 2 * GiB}, zfs_errors("zfs.resource.set.properties.refreservation"), "volsize"),
        (
            "FILESYSTEM",
            {"user_properties_update": [{"key": "custom:x", "remove": True}]},
            zfs_errors("zfs.resource.set.inherit.custom:x"),
            "user_properties_update",
        ),
        (
            "FILESYSTEM",
            {"user_properties_update": [{"key": "custom:x", "value": "a"}]},
            ValidationError("zfs.resource.set.user_properties", "bad value", errno.EINVAL),
            "user_properties_update",
        ),
        ("FILESYSTEM", {"atime": "OFF"}, ValidationError("zfs.resource.set.path", "gone", errno.ENOENT), None),
        ("FILESYSTEM", {"atime": "OFF"}, zfs_errors("zfs.resource.set.properties"), None),
    ],
)
async def test_update_rekeys_each_error_class(dataset_type, data, error, expected):
    _, svc = make_service(error, dataset_type=dataset_type)

    with pytest.raises(ValidationErrors) as ve:
        await update(svc, data)

    assert [e.attribute for e in ve.value.errors] == [
        f"pool_dataset_update.{expected}" if expected else "pool_dataset_update"
    ]


async def test_update_batches_shim_and_zfs_errors_through_dry_run():
    requests = []

    def zfs_set(data):
        requests.append(data)
        raise zfs_errors("zfs.resource.set.properties.recordsize")

    middleware, svc = make_service(zfs_set)

    with pytest.raises(ValidationErrors) as ve:
        await update(
            svc,
            {
                "user_properties": [{"key": "custom:a", "value": "1"}],
                "user_properties_update": [{"key": "custom:b", "value": "2"}],
                "recordsize": "3000",
            },
        )

    assert [e.attribute for e in ve.value.errors] == [
        "pool_dataset_update.user_properties_update",
        "pool_dataset_update.recordsize",
    ]
    assert [request.dry_run for request in requests] == [True]
    middleware.send_event.assert_not_called()


async def test_update_reports_values_the_zfs_model_rejects():
    middleware, svc = make_service()

    with pytest.raises(ValidationErrors) as ve:
        await update(svc, {"copies": 7})

    assert [(e.attribute, e.errno) for e in ve.value.errors] == [("pool_dataset_update.copies", errno.EINVAL)]
    middleware.services.zfs.resource.set.assert_not_called()


async def test_update_with_empty_payload_skips_zfs_and_emits_changed():
    middleware, svc = make_service()

    entry = await update(svc, {})

    assert entry["id"] == "tank/ds"
    middleware.services.zfs.resource.set.assert_not_called()
    middleware.send_event.assert_called_once()
    assert middleware.send_event.call_args.args == ("pool.dataset.query", "CHANGED")
