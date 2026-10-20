import asyncio
import errno
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import generic_sharing_service, sharing_service, sharing_task_service_part
from middlewared.service.sharing_task_service_part import resolve_stored_paths
from middlewared.utils import mount
from middlewared.utils.filter_list import filter_list
from middlewared.utils.mount import resolve_dataset_path


@pytest.fixture
def fs(monkeypatch):
    """Paths that exist, each mapped to the statmount result of the mount that holds it."""
    paths = {}
    fds = {}

    def openat2(path, flags, resolve):
        if path not in paths:
            raise FileNotFoundError(errno.ENOENT, path)
        fd = os.open("/dev/null", os.O_RDONLY)
        fds[fd] = path
        return fd

    monkeypatch.setattr(
        mount,
        "truenas_os",
        SimpleNamespace(
            openat2=openat2,
            statx=lambda path, dir_fd, flags, mask: SimpleNamespace(stx_mnt_id=fds[dir_fd]),
            statmount=lambda mnt_id, mask: paths[mnt_id],
            RESOLVE_NO_SYMLINKS=0,
            AT_EMPTY_PATH=0,
            STATX_BASIC_STATS=0,
            STATX_MNT_ID_UNIQUE=0,
            STATMOUNT_MNT_POINT=0,
            STATMOUNT_MNT_ROOT=0,
            STATMOUNT_FS_TYPE=0,
            STATMOUNT_SB_SOURCE=0,
        ),
    )

    def add(path, mnt_point, source, fs_type="zfs", mnt_root="/"):
        paths[path] = SimpleNamespace(mnt_point=mnt_point, sb_source=source, fs_type=fs_type, mnt_root=mnt_root)

    return add


def zfs_middleware(*datasets):
    """A middleware whose ZFS holds `datasets`, each a (name, mountpoint, canmount) tuple."""
    middleware = Middleware()
    middleware.services.zfs.resource.list_impl = Mock(
        side_effect=lambda query: [
            {
                "name": name,
                "type": "FILESYSTEM",
                "properties": {"mountpoint": {"raw": mountpoint}, "canmount": {"raw": canmount}},
            }
            for name, mountpoint, canmount in datasets
            if name in query.paths
        ]
    )
    return middleware


def test_dataset_root(fs):
    fs("/mnt/tank/ds", "/mnt/tank/ds", "tank/ds")
    middleware = zfs_middleware()
    assert resolve_dataset_path("/mnt/tank/ds/", middleware) == ("tank/ds", "")
    middleware.services.zfs.resource.list_impl.assert_not_called()


@pytest.mark.parametrize(
    "path,datasets,expected",
    [
        ("/mnt/tank/ds/a/b", [], ("tank/ds", "a/b")),
        # an unmounted child's mountpoint, e.g. a locked dataset whose immutable flag could not be set
        ("/mnt/tank/ds/child", [("tank/ds/child", "/mnt/tank/ds/child", "on")], ("tank/ds/child", "")),
        ("/mnt/tank/ds/child", [("tank/ds/child", "/mnt/tank/ds/child", "noauto")], ("tank/ds/child", "")),
        ("/mnt/tank/ds/child", [("tank/ds/child", "/mnt/tank/ds/child", "off")], ("tank/ds", "child")),
        ("/mnt/tank/ds/child", [("tank/ds/child", "/mnt/elsewhere", "on")], ("tank/ds", "child")),
        # below a locked child, where only the child's mountpoint exists
        (
            "/mnt/tank/ds/child/grandchild/dir",
            [
                ("tank/ds/child", "/mnt/tank/ds/child", "on"),
                ("tank/ds/child/grandchild", "/mnt/tank/ds/child/grandchild", "on"),
            ],
            ("tank/ds/child/grandchild", "dir"),
        ),
    ],
)
def test_unmounted_children(fs, path, datasets, expected):
    fs("/mnt/tank/ds/a/b", "/mnt/tank/ds", "tank/ds")
    fs("/mnt/tank/ds/child", "/mnt/tank/ds", "tank/ds")
    assert resolve_dataset_path(path, zfs_middleware(*datasets)) == expected


def test_invalid_dataset_name_is_not_looked_up(fs):
    fs("/mnt/tank/ds/a@b/c", "/mnt/tank/ds", "tank/ds")
    middleware = zfs_middleware()
    assert resolve_dataset_path("/mnt/tank/ds/a@b/c", middleware) == ("tank/ds", "a@b/c")
    middleware.services.zfs.resource.list_impl.assert_not_called()


@pytest.mark.parametrize(
    "mount_args",
    [
        ("/mnt/tank/ds/.zfs/snapshot/snap", "tank/ds@snap"),
        ("/mnt/tank/ds", "tmpfs", "tmpfs"),
        ("/", "boot-pool/ROOT/28.0"),
    ],
    ids=["snapshot", "not-zfs", "boot-pool"],
)
def test_not_a_data_pool_dataset(fs, mount_args):
    fs("/mnt/tank/ds/x", *mount_args)
    assert resolve_dataset_path("/mnt/tank/ds/x", zfs_middleware()) == (None, None)


def test_bind_mount(fs):
    fs("/mnt/tank/ds/x", "/mnt/tank/ds", "tank/other", "zfs", "/subdir")
    middleware = zfs_middleware()
    assert resolve_dataset_path("/mnt/tank/ds/x", middleware) == ("tank/other", "subdir/x")
    middleware.services.zfs.resource.list_impl.assert_not_called()


def test_locked_pool_root(fs):
    fs("/mnt/tank", "/", "boot-pool/ROOT/28.0")
    middleware = zfs_middleware(("tank", "/mnt/tank", "on"), ("tank/ds", "/mnt/tank/ds", "on"))
    assert resolve_dataset_path("/mnt/tank/ds/x", middleware) == ("tank/ds", "x")


def test_nothing_exists(fs):
    assert resolve_dataset_path("/mnt/tank/ds/x", zfs_middleware()) == (None, None)


@pytest.fixture
def table(monkeypatch):
    rows = [
        {"id": 1, "p_path": "/mnt/tank/a/dir", "p_dataset": "tank", "p_relative_path": "a/dir"},
        {"id": 2, "p_path": "/mnt/tank/b", "p_dataset": "tank/b", "p_relative_path": ""},
        {"id": 3, "p_path": "/mnt/tank/c", "p_dataset": None, "p_relative_path": None},
        {"id": 4, "p_path": "/mnt/tank/gone", "p_dataset": "tank", "p_relative_path": "gone"},
        {"id": 5, "p_path": "/dev/zvol/tank/vol", "p_dataset": None, "p_relative_path": None},
        {"id": 6, "p_path": "/mnt/other/d", "p_dataset": "other/d", "p_relative_path": ""},
        {"id": 7, "p_path": "/mnt/tank/a", "p_dataset": "tank/a", "p_relative_path": ""},
        {"id": 8, "p_path": "/mnt/tank/a/sub/x", "p_dataset": "tank/a/sub", "p_relative_path": "x"},
    ]
    resolved = {
        "/mnt/tank/a/dir": ("tank/a", "dir"),
        "/mnt/tank/b": ("tank/b", ""),
        "/mnt/tank/c": ("tank/c", ""),
        "/mnt/tank/gone": (None, None),
        "/mnt/other/d": ("other/d2", ""),
        "/mnt/tank/a": ("tank/a", ""),
        "/mnt/tank/a/sub/x": ("tank/a/sub/x", ""),
    }
    resolve = Mock(side_effect=lambda path, middleware: resolved[path])
    monkeypatch.setattr(sharing_task_service_part, "resolve_dataset_path", resolve)

    middleware = Middleware()
    middleware["datastore.query"] = lambda datastore, filters: filter_list(rows, filters)
    middleware["datastore.update"] = Mock()
    return SimpleNamespace(middleware=middleware, resolve=resolve, rows=rows)


async def resolve(table, **kwargs):
    return await resolve_stored_paths(table.middleware, "test", "test.table", "p_", "path", None, **kwargs)


@pytest.mark.asyncio
async def test_resolve_stored_paths_updates_changed_rows(table):
    assert await resolve(table) == [1, 3, 6, 8]
    assert [call.args for call in table.middleware["datastore.update"].call_args_list] == [
        ("test.table", 1, {"p_dataset": "tank/a", "p_relative_path": "dir"}),
        ("test.table", 3, {"p_dataset": "tank/c", "p_relative_path": ""}),
        ("test.table", 6, {"p_dataset": "other/d2", "p_relative_path": ""}),
        ("test.table", 8, {"p_dataset": "tank/a/sub/x", "p_relative_path": ""}),
    ]
    # a zvol source is never resolved
    assert "/dev/zvol/tank/vol" not in [call.args[0] for call in table.resolve.call_args_list]


@pytest.mark.asyncio
async def test_resolve_stored_paths_after_unlock(table):
    # unresolved rows, and rows on the unlocked dataset, above it or inside it
    assert await resolve(table, datasets=["tank/a"]) == [1, 3, 8]
    assert [call.args[0] for call in table.resolve.call_args_list] == [
        "/mnt/tank/a/dir",
        "/mnt/tank/c",
        "/mnt/tank/gone",
        "/mnt/tank/a",
        "/mnt/tank/a/sub/x",
    ]


@pytest.mark.asyncio
async def test_resolve_stored_paths_after_mount(table):
    assert await resolve(table, mountpoints={"/mnt/tank/a", "/mnt/other/d"}) == [1, 6, 8]
    assert [call.args[0] for call in table.resolve.call_args_list] == [
        "/mnt/tank/a/dir",
        "/mnt/other/d",
        "/mnt/tank/a",
        "/mnt/tank/a/sub/x",
    ]


@pytest.mark.asyncio
async def test_resolve_stored_paths_skips_a_row_whose_path_changed(table):
    resolve_unchanged = table.resolve.side_effect

    def resolve_while_path_changes(path, middleware):
        table.rows[0]["p_path"] = "/mnt/tank/new"
        return resolve_unchanged(path, middleware)

    table.resolve.side_effect = resolve_while_path_changes
    assert 1 not in await resolve(table)
    assert 1 not in [call.args[1] for call in table.middleware["datastore.update"].call_args_list]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module,base",
    [
        (sharing_service, sharing_service.SharingTaskService),
        (generic_sharing_service, generic_sharing_service.GenericSharingTaskService),
    ],
)
async def test_mounts_resolve_together(monkeypatch, module, base):
    monkeypatch.setattr(module, "MOUNT_RESOLVE_DELAY", 0.01)
    service = SimpleNamespace(_mounted_unresolved=set(), resolve_paths=AsyncMock())
    middleware = Middleware()

    await asyncio.gather(
        *(base.resolve_mounted_paths(service, middleware, {"mountpoint": mp}) for mp in ("/mnt/a", "/mnt/b"))
    )
    await base.resolve_mounted_paths(service, middleware, {"mountpoint": "/mnt/c"})

    assert [call.kwargs["mountpoints"] for call in service.resolve_paths.call_args_list] == [
        {"/mnt/a", "/mnt/b"},
        {"/mnt/c"},
    ]
