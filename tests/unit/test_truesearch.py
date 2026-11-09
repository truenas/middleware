import asyncio
import base64
from datetime import datetime, timezone
import errno
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from truenas_pylicensed.features import LicenseFeature
import truesearch_client
from truesearch_client.config import TargetRow
from truesearch_client.control import IndexerStatus, IndexerTarget, UnindexedTarget

from middlewared.api.current import TruesearchQuery
import middlewared.plugins.truesearch as truesearch_plugin
from middlewared.plugins.truesearch import (
    DatasetInfo,
    TrueSearchFSAttachmentDelegate,
    TrueSearchService,
    beneath,
    carried_rows,
)
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import FakeJob, Middleware
from middlewared.service import CallError, ValidationError
from middlewared.utils.truesearch_filters import spotlight_query

BOOT_POOL_REASON = "The system dataset must not reside on the boot pool."
# The message for a system without a license. The denial columns below must use it. A license without the TrueSearch
# key gives a different message.
NOT_LICENSED = "This system is not licensed to use the TrueSearch feature."


def zfs_list(names: list[str]) -> list[dict]:
    """The answer of zfs.resource.list_impl for the filesystems `names`."""
    return [
        {"name": name, "type": "FILESYSTEM", "properties": {"mountpoint": {"value": f"/mnt/{name}"}}} for name in names
    ]


@pytest.mark.asyncio
async def test_datasets_leave_out_a_legacy_mountpoint():
    middleware = Mock()
    middleware.call2 = AsyncMock(
        return_value=[
            {"name": "tank/legacy", "type": "FILESYSTEM", "properties": {"mountpoint": {"value": "legacy"}}},
            *zfs_list(["tank/users"]),
        ]
    )
    assert list(await TrueSearchService(middleware).datasets({"tank"})) == ["/mnt/tank/users"]


@pytest.mark.parametrize(
    "directory,datasets,result",
    [
        ("/mnt/tank/users", ["tank"], {"/mnt/tank/users"}),
        ("/mnt/tank/users/alex", ["tank", "tank/users"], {"/mnt/tank/users/alex"}),
        # Each dataset beneath a share directory is indexed too.
        (
            "/mnt/tank/users",
            ["tank", "tank/users", "tank/users/alice", "tank/users/alice/books", "tank/users/bob"],
            {"/mnt/tank/users", "/mnt/tank/users/alice", "/mnt/tank/users/alice/books", "/mnt/tank/users/bob"},
        ),
        # The share directory does not have to be the mountpoint of a dataset.
        ("/mnt/tank/shares", ["tank", "tank/shares/media"], {"/mnt/tank/shares", "/mnt/tank/shares/media"}),
        # A directory in no dataset gives nothing.
        ("/mnt/gone/x", ["tank"], set()),
    ],
)
def test_processed_directories_for_directory(directory, datasets, result):
    mountpoints = {f"/mnt/{name}": DatasetInfo(name, "1") for name in datasets}
    assert TrueSearchService(Mock())._processed_directories_for_directory(mountpoints, directory) == result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "directories,result",
    [
        ({"/mnt/tank/users"}, True),
        # A share directory in no dataset is not indexed.
        ({"/mnt/gone/x"}, False),
        (set(), False),
    ],
)
async def test_enabled_when_a_share_is_in_a_dataset(directories, result):
    svc = TrueSearchService(Mock())
    svc.available = AsyncMock(return_value=True)
    svc.raw_directories = AsyncMock(return_value=directories)
    svc.datasets = AsyncMock(return_value={"/mnt/tank": DatasetInfo("tank", "1")})
    assert await svc.enabled() is result


@pytest.mark.asyncio
async def test_unavailable_reasons_omits_licensing_reason_when_entitled(monkeypatch):
    monkeypatch.setattr(truesearch_plugin, "_index_dataset_mounted", lambda: True)
    m = Middleware()
    m["systemdataset.is_boot_pool"] = lambda *args: False
    checked = install_entitlements_for_column(m, LicenseFeature.TRUESEARCH, "HW+K")

    assert await create_service(m, TrueSearchService).unavailable_reasons() == []
    assert checked == [LicenseFeature.TRUESEARCH]


@pytest.mark.asyncio
async def test_unavailable_reasons_reports_boot_pool_and_licensing_together(monkeypatch):
    monkeypatch.setattr(truesearch_plugin, "_index_dataset_mounted", lambda: True)
    m = Middleware()
    m["systemdataset.is_boot_pool"] = lambda *args: True
    install_entitlements_for_column(m, LicenseFeature.TRUESEARCH, "CE")

    assert await create_service(m, TrueSearchService).unavailable_reasons() == [BOOT_POOL_REASON, NOT_LICENSED]


@pytest.mark.asyncio
async def test_unavailable_reasons_reports_an_index_dataset_that_is_not_mounted(monkeypatch):
    # setup_datasets did not mount the index dataset, for example because the pwenc secret does not unlock it.
    monkeypatch.setattr(truesearch_plugin, "_index_dataset_mounted", lambda: False)
    m = Middleware()
    m["systemdataset.is_boot_pool"] = lambda *args: False
    m.services.truenas.entitlements.check = AsyncMock(return_value=SimpleNamespace(entitled=True, message=""))
    assert await TrueSearchService(m).unavailable_reasons() == [
        "The TrueSearch index dataset is not mounted. The middleware log gives the reason.",
    ]


@pytest.fixture
def truesearch(monkeypatch):
    monkeypatch.setattr(TrueSearchService, "MOUNT_CHECK_DELAY", 0.01)
    m = Middleware()
    m.create_task = asyncio.create_task
    svc = TrueSearchService(m)
    svc.raw_directories = AsyncMock(return_value={"/mnt/tank/share"})
    svc.configure = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_burst_of_mounts_is_checked_once(truesearch):
    await truesearch.schedule_mount_check("/mnt/tank/share/ds0")
    first_timer = truesearch.mount_check_timer
    for i in range(1, 100):
        await truesearch.schedule_mount_check(f"/mnt/tank/share/ds{i}")
    # Each mount restarts the delay.
    assert first_timer.cancelled()
    # The last timer started before this sleep, with a shorter delay. So the check runs first.
    await asyncio.sleep(0.1)
    truesearch.raw_directories.assert_awaited_once()
    truesearch.configure.assert_awaited_once()


@pytest.mark.asyncio
async def test_mount_during_a_check_is_checked_by_the_next_one(truesearch):
    later_mounts = ["/mnt/tank/share/child"]

    async def raw_directories():
        # Another dataset mounts while the check reads the directories.
        if later_mounts:
            await truesearch.schedule_mount_check(later_mounts.pop())
        return {"/mnt/tank/share"}

    truesearch.raw_directories = raw_directories
    await truesearch.schedule_mount_check("/mnt/tank/other")
    # Run the checks of the timers one after the other. Do not wait for the timers.
    await truesearch.check_mounted_paths()
    truesearch.configure.assert_not_awaited()
    await truesearch.check_mounted_paths()
    truesearch.configure.assert_awaited_once()
    # Cancel the timer of the second mount before the test ends.
    truesearch.mount_check_timer.cancel()


@pytest.mark.asyncio
async def test_smb_home_shares_are_not_indexed():
    m = Middleware()
    m["smb.config"] = Mock(return_value={"search_protocols": ["SPOTLIGHT"]})
    m.services.service.started_or_enabled = AsyncMock(return_value=True)
    m["sharing.smb.query"] = Mock(
        return_value=[
            {"path": "/mnt/tank/data", "locked": False, "purpose": "DEFAULT_SHARE", "options": {}},
            {
                "path": "/mnt/tank/homes",
                "locked": False,
                "purpose": "LEGACY_SHARE",
                "options": {"home": True, "timemachine": False},
            },
            {"path": "/mnt/tank/private", "locked": False, "purpose": "PRIVATE_DATASETS_SHARE", "options": {}},
        ]
    )
    svc = TrueSearchService(m)
    assert await svc.smb_directories() == {"/mnt/tank/data"}
    assert await svc.smb_directories(enabled_only=False) == {"/mnt/tank/data"}


@pytest.mark.asyncio
async def test_a_legacy_time_machine_share_is_not_indexed():
    m = Middleware()
    m["smb.config"] = Mock(return_value={"search_protocols": ["SPOTLIGHT"]})
    m.services.service.started_or_enabled = AsyncMock(return_value=True)
    m["sharing.smb.query"] = Mock(
        return_value=[
            {"path": "/mnt/tank/data", "locked": False, "purpose": "DEFAULT_SHARE", "options": {}},
            {
                "path": "/mnt/tank/data/tm",
                "locked": False,
                "purpose": "LEGACY_SHARE",
                "options": {"home": False, "timemachine": True},
            },
        ]
    )
    svc = TrueSearchService(m)
    assert await svc.smb_directories() == {"/mnt/tank/data"}
    # It is excluded from the row of its dataset.
    assert await svc.timemachine_directories() == {"/mnt/tank/data/tm"}


@pytest.mark.asyncio
async def test_the_webshare_home_base_is_not_indexed():
    m = Middleware()
    m.services.webshare.config = AsyncMock(return_value=Mock(search=True))
    m.services.service.started_or_enabled = AsyncMock(return_value=True)
    m.services.sharing.webshare.query = AsyncMock(
        return_value=[
            SimpleNamespace(path="/mnt/tank/data", locked=False, is_home_base=False),
            SimpleNamespace(path="/mnt/tank/homes", locked=False, is_home_base=True),
        ]
    )
    svc = TrueSearchService(m)
    assert await svc.webshare_directories() == {"/mnt/tank/data"}
    assert await svc.webshare_directories(enabled_only=False) == {"/mnt/tank/data"}


@pytest.mark.asyncio
async def test_service_state_is_not_queried_when_search_is_off():
    m = Middleware()
    m["smb.config"] = Mock(return_value={"search_protocols": []})
    m.services.webshare.config = AsyncMock(return_value=Mock(search=False))
    m.services.service.started_or_enabled = AsyncMock(return_value=True)
    assert await TrueSearchService(m).raw_directories() == set()
    m.services.service.started_or_enabled.assert_not_awaited()


# The datasets of the target tests, by mountpoint.
DATASETS = {
    "/mnt/tank": DatasetInfo("tank", "1"),
    "/mnt/tank/data": DatasetInfo("tank/data", "2"),
    "/mnt/tank/data/media": DatasetInfo("tank/data/media", "3"),
    "/mnt/tank/data/secret": DatasetInfo("tank/data/secret", "4"),
    "/mnt/tank/other": DatasetInfo("tank/other", "5"),
    "/mnt/tank/other/dir/child": DatasetInfo("tank/other/dir/child", "6"),
}


def target_service(monkeypatch, indexed, shared=None, old=None, imported=("tank",), locked=("tank/data/secret",)):
    m = Middleware()
    # zfs.resource.path_is_locked answers True for the datasets of `locked`.
    m.services.zfs.resource.path_is_locked = AsyncMock(side_effect=lambda name: name in locked)
    svc = TrueSearchService(m)
    svc.raw_directories = AsyncMock(
        side_effect=lambda enabled_only=True: indexed if enabled_only or shared is None else shared,
    )
    svc.timemachine_directories = AsyncMock(return_value={"/mnt/tank/data/tm", "/mnt/tank/other/tm"})
    svc.datasets = AsyncMock(return_value=DATASETS)
    monkeypatch.setattr(truesearch_plugin, "read_config", lambda: old)
    monkeypatch.setattr(
        truesearch_plugin,
        "query_imported_fast_impl",
        lambda: {str(guid): {"name": name, "state": "ONLINE"} for guid, name in enumerate(imported)},
    )
    return svc


@pytest.mark.asyncio
async def test_targets_one_row_per_dataset_at_the_directory_its_shares_share(monkeypatch):
    svc = target_service(
        monkeypatch,
        {
            "/mnt/tank/data/a",
            "/mnt/tank/data/b",
            "/mnt/tank/data/media",
            "/mnt/tank/data/secret/x",
        },
    )
    assert await svc.targets() == [
        TargetRow(id="ds2", dataset="tank/data", root="/mnt/tank/data", exclude=("tm",)),
        TargetRow(id="ds3", dataset="tank/data/media", root="/mnt/tank/data/media"),
        # A locked dataset keeps a disabled row, and so keeps its index.
        TargetRow(id="ds4", dataset="tank/data/secret", root="/mnt/tank/data/secret/x", enabled=False),
    ]


@pytest.mark.asyncio
async def test_targets_add_the_datasets_beneath_a_directory_share(monkeypatch):
    svc = target_service(monkeypatch, {"/mnt/tank/other/dir"})
    assert await svc.targets() == [
        TargetRow(id="ds5", dataset="tank/other", root="/mnt/tank/other/dir"),
        TargetRow(id="ds6", dataset="tank/other/dir/child", root="/mnt/tank/other/dir/child"),
    ]


@pytest.mark.asyncio
async def test_targets_disable_a_dataset_beneath_a_share_that_is_about_to_be_locked(monkeypatch):
    # The share is on tank/data, which is not locked. Its child dataset tank/data/media is about to be locked.
    svc = target_service(monkeypatch, {"/mnt/tank/data"}, locked=("tank/data/media", "tank/data/secret"))
    assert await svc.targets() == [
        TargetRow(id="ds2", dataset="tank/data", root="/mnt/tank/data", exclude=("tm",)),
        TargetRow(id="ds3", dataset="tank/data/media", root="/mnt/tank/data/media", enabled=False),
        TargetRow(id="ds4", dataset="tank/data/secret", root="/mnt/tank/data/secret", enabled=False),
    ]


@pytest.mark.asyncio
async def test_targets_of_nothing_look_up_no_dataset(monkeypatch):
    svc = target_service(monkeypatch, set())
    assert await svc.targets() == []
    svc.datasets.assert_not_awaited()


@pytest.mark.asyncio
async def test_targets_keep_a_disabled_row_for_a_dataset_whose_shares_are_disabled(monkeypatch):
    svc = target_service(monkeypatch, {"/mnt/tank/data/a"}, {"/mnt/tank/data/a", "/mnt/tank/other/b"})
    assert await svc.targets() == [
        TargetRow(id="ds2", dataset="tank/data", root="/mnt/tank/data/a"),
        TargetRow(id="ds5", dataset="tank/other", root="/mnt/tank/other/b", enabled=False),
    ]


@pytest.mark.asyncio
async def test_targets_carry_the_rows_of_a_pool_that_is_not_imported(monkeypatch):
    old = [
        TargetRow(id="ds8", dataset="gone/x", root="/mnt/gone/x"),
        TargetRow(id="ds9", dataset="gone/y", root="/mnt/gone/y"),
        TargetRow(id="ds7", dataset="tank/destroyed", root="/mnt/tank/destroyed"),
    ]
    svc = target_service(
        monkeypatch,
        {"/mnt/tank/data/a"},
        {"/mnt/tank/data/a", "/mnt/gone/x/share", "/mnt/tank/destroyed"},
        old,
    )
    assert await svc.targets() == [
        # The share of the destroyed dataset is in the dataset above it now. ds7 is not carried: tank is imported.
        TargetRow(id="ds1", dataset="tank", root="/mnt/tank/destroyed", enabled=False),
        TargetRow(id="ds2", dataset="tank/data", root="/mnt/tank/data/a"),
        TargetRow(id="ds8", dataset="gone/x", root="/mnt/gone/x", enabled=False),
    ]


@pytest.mark.asyncio
async def test_targets_disable_the_rows_beneath_a_mountpoint_being_destroyed(monkeypatch):
    svc = target_service(monkeypatch, {"/mnt/tank/data/a", "/mnt/tank/data/media"})
    svc.releasing.append("/mnt/tank/data/media")
    assert await svc.targets() == [
        TargetRow(id="ds2", dataset="tank/data", root="/mnt/tank/data/a"),
        TargetRow(id="ds3", dataset="tank/data/media", root="/mnt/tank/data/media", enabled=False),
    ]


def rows(*ids, disabled=()):
    return [
        TargetRow(id=id_, dataset=f"tank/{id_}", root=f"/mnt/tank/{id_}", enabled=id_ not in disabled) for id_ in ids
    ]


def configured(monkeypatch, enabled, running, files):
    m = Middleware()
    m.services.service.started = AsyncMock(return_value=running)
    m.services.service.control = AsyncMock(return_value=FakeJob())
    svc = TrueSearchService(m)
    svc.enabled = AsyncMock(return_value=enabled)
    files = iter(files)
    monkeypatch.setattr(truesearch_plugin, "read_config", lambda: next(files))
    sent = []
    monkeypatch.setattr(truesearch_plugin, "control_request", lambda path, line: sent.append(line) or "dropped")
    waited = []
    monkeypatch.setattr(truesearch_plugin, "devices_of", set)
    monkeypatch.setattr(truesearch_plugin, "wait_released", lambda devices: waited.append(devices) or True)
    return m, svc, sent, waited


@pytest.mark.asyncio
async def test_configure_drops_the_index_targets_that_left(monkeypatch):
    m, svc, sent, waited = configured(monkeypatch, True, True, [rows("ds1", "ds2"), rows("ds2")])
    await svc.configure()
    m.services.service.control.assert_awaited_once_with("RELOAD", "truesearch")
    assert waited == [{"/mnt/tank/ds1"}]
    assert sent == ["drop ds1"]


@pytest.mark.asyncio
async def test_configure_keeps_the_index_of_a_disabled_row(monkeypatch):
    files = [rows("ds1", "ds2"), rows("ds1", "ds2", disabled={"ds1"})]
    m, svc, sent, waited = configured(monkeypatch, True, True, files)
    await svc.configure()
    assert waited == [{"/mnt/tank/ds1"}]
    assert sent == []


@pytest.mark.asyncio
async def test_configure_waits_for_nothing_when_no_row_was_released(monkeypatch):
    m, svc, sent, waited = configured(monkeypatch, True, True, [rows("ds1", disabled={"ds1"}), rows("ds1")])
    await svc.configure()
    assert (waited, sent) == ([], [])


@pytest.mark.asyncio
async def test_configure_drops_nothing_when_it_stops(monkeypatch):
    m, svc, sent, waited = configured(monkeypatch, False, True, [rows("ds1"), []])
    await svc.configure()
    m.services.service.control.assert_awaited_once_with("STOP", "truesearch")
    assert (waited, sent) == ([], [])


@pytest.mark.asyncio
async def test_configure_drops_nothing_when_no_file_was_written(monkeypatch):
    m, svc, sent, waited = configured(monkeypatch, True, False, [rows("ds1"), None])
    await svc.configure()
    m.services.service.control.assert_awaited_once_with("START", "truesearch")
    assert (waited, sent) == ([], [])


@pytest.mark.asyncio
async def test_configure_waits_for_nothing_when_it_starts(monkeypatch):
    m, svc, sent, waited = configured(monkeypatch, True, False, [rows("ds1"), rows("ds2")])
    await svc.configure()
    assert (waited, sent) == ([], ["drop ds1"])


def releasing_service(monkeypatch, running=True):
    m = Middleware()
    m.services.service.started = AsyncMock(return_value=running)
    svc = TrueSearchService(m)
    monkeypatch.setattr(truesearch_plugin, "read_config", lambda: rows("ds1", "ds2", disabled={"ds2"}))
    seen = []

    async def configure():
        seen.append(list(svc.releasing))

    svc.configure = configure
    return svc, seen


@pytest.mark.asyncio
async def test_remove_mountpoint_releases_the_rows_beneath_it(monkeypatch):
    svc, seen = releasing_service(monkeypatch)
    async with svc.remove_mountpoint("/mnt/tank/ds1"):
        assert seen == [["/mnt/tank/ds1"]]

    assert seen == [["/mnt/tank/ds1"], []]


@pytest.mark.asyncio
async def test_remove_mountpoint_configures_again_when_the_destroy_fails(monkeypatch):
    svc, seen = releasing_service(monkeypatch)
    with pytest.raises(OSError):
        async with svc.remove_mountpoint("/mnt/tank"):
            raise OSError(errno.EBUSY, "busy")

    assert seen == [["/mnt/tank"], []]


@pytest.mark.parametrize(
    "mountpoint,running", [("/mnt/tank/ds2", True), ("/mnt/tank/ds3", True), (None, True), ("/mnt/tank/ds1", False)]
)
@pytest.mark.asyncio
async def test_remove_mountpoint_of_nothing_held_changes_nothing(monkeypatch, mountpoint, running):
    svc, seen = releasing_service(monkeypatch, running)
    async with svc.remove_mountpoint(mountpoint):
        pass

    assert seen == []


@pytest.mark.asyncio
async def test_attachments_are_the_rows_both_daemons_hold(monkeypatch):
    m = Middleware()
    m.services.service.started = AsyncMock(return_value=True)
    monkeypatch.setattr(
        truesearch_plugin,
        "read_config",
        lambda: rows("ds1", "ds2", disabled={"ds2"}) + [TargetRow(id="ds3", dataset="other/x", root="/mnt/other/x")],
    )
    delegate = TrueSearchFSAttachmentDelegate(m)
    assert await delegate.query("/mnt/tank", True) == rows("ds1")
    assert await delegate.query("/mnt/tank/ds1", True, {"exact_match": True}) == rows("ds1")
    assert await delegate.query("/mnt/tank", False) == []
    assert await delegate.get_attachment_name(rows("ds1")[0]) == "tank/ds1"

    m.services.service.started = AsyncMock(return_value=False)
    assert await delegate.query("/mnt/tank", True) == []


class FakeClient:
    requests: list = []
    hits: tuple = ()
    error: Exception | None = None
    # Hits and errors for one dataset, by its name.
    hits_by_dataset: dict = {}
    errors_by_dataset: dict = {}

    def __init__(self, *args):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def search(self, request):
        FakeClient.requests.append(request)
        if (error := FakeClient.errors_by_dataset.get(request.dataset, FakeClient.error)) is not None:
            raise error
        return SimpleNamespace(hits=FakeClient.hits_by_dataset.get(request.dataset, FakeClient.hits), truncated=False)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(truesearch_plugin, "Client", FakeClient)
    FakeClient.requests, FakeClient.hits, FakeClient.error = [], (), None
    FakeClient.hits_by_dataset, FakeClient.errors_by_dataset = {}, {}
    monkeypatch.setattr(truesearch_plugin, "read_config", lambda: SEARCH_ROWS)
    return truesearch_client


# The rows of the configuration file in the search tests.
SEARCH_ROWS = [
    TargetRow(id="ds2", dataset="tank/data", root="/mnt/tank/data/shares"),
    TargetRow(id="ds3", dataset="tank/off", root="/mnt/tank/off", enabled=False),
    # A child dataset beneath the share, with an index of its own.
    TargetRow(id="ds4", dataset="tank/data/shares/media", root="/mnt/tank/data/shares/media"),
]


# The details of the user of the search tests, as user.get_user_obj gives them.
USER_DETAILS = {"pw_name": "alex", "pw_uid": 1000, "pw_gid": 1001, "grouplist": [1001, 2000]}


def search_service():
    m = Middleware()
    m.services.zfs.resource.list_impl = Mock(
        return_value=[
            {"name": "tank/data", "type": "FILESYSTEM", "properties": {"mountpoint": {"value": "/mnt/tank/data"}}},
            {
                "name": "tank/data/shares/media",
                "type": "FILESYSTEM",
                "properties": {"mountpoint": {"value": "/mnt/tank/data/shares/media"}},
            },
        ]
    )
    m.services.user.get_user_obj = Mock(
        return_value=SimpleNamespace(
            pw_uid=1000,
            pw_gid=1001,
            grouplist=[1001, 2000],
            model_dump=lambda: USER_DETAILS,
        )
    )
    m["filesystem.can_access_as_cred_errors"] = Mock(return_value=[])
    return m, TrueSearchService(m)


def query(svc, path="/mnt/tank/data/shares", filters=(), options=None, **fields):
    return svc.query(
        TruesearchQuery.model_validate(
            {
                "path": path,
                "query-filters": list(filters),
                "query-options": {"limit": 10} if options is None else options,
                **fields,
            }
        )
    )


def stat(**fields):
    """A stat that truesearchd returns. A field that is not given has a test value."""
    return truesearch_client.Stat(
        **{
            "file_id": 0,
            "volume_id": 0,
            "mode": 0o100644,
            "size": 5,
            "uid": 0,
            "gid": 0,
            "mtime_sec": 1_700_000_000,
            "mtime_nsec": 0,
            "btime_sec": 1_600_000_000,
            "btime_nsec": 0,
            "atime_sec": 1_700_000_100,
            "atime_nsec": 0,
            "ino": 1234,
            "generation": 98765,
            **fields,
        }
    )


def test_query_as_root(client):
    m, svc = search_service()
    FakeClient.hits = (SimpleNamespace(path="q3/report.pdf", st=stat()),)
    entries = query(svc, filters=[["name", "Crin", 're"port']])
    request = FakeClient.requests[0]
    assert (request.dataset, request.share) == ("tank/data", "shares")
    assert request.query == spotlight_query([["name", "Crin", 're"port']])
    assert (request.who.uid, request.who.gid, request.who.gids, request.max_results) == (0, 0, (), 10)
    entry = entries[0]
    assert (entry.path, entry.name, entry.type, entry.size) == (
        "/mnt/tank/data/shares/q3/report.pdf",
        "report.pdf",
        "FILE",
        5,
    )
    assert entry.btime == datetime.fromtimestamp(1_600_000_000, tz=timezone.utc)
    assert (entry.inode, base64.b64decode(entry.handle)) == (1234, stat().handle)
    m["filesystem.can_access_as_cred_errors"].assert_not_called()


def test_query_reads_the_indexed_datasets_once(client):
    m, svc = search_service()
    query(svc)
    query(svc, path="/mnt/tank/data/shares/media")
    with pytest.raises(CallError):
        query(svc, path="/mnt/tank/elsewhere")
    # One listing of the mountpoints serves every query until the cache is cleared.
    assert m.services.zfs.resource.list_impl.call_count == 1
    assert len(FakeClient.requests) == 2


@pytest.mark.asyncio
async def test_configure_forgets_the_indexed_datasets(monkeypatch):
    m, svc, sent, waited = configured(monkeypatch, True, True, [rows("ds1"), rows("ds1")])
    svc._indexed = []
    await svc.configure()
    assert svc._indexed is None


@pytest.mark.asyncio
async def test_a_mount_forgets_the_indexed_datasets(truesearch):
    truesearch._indexed = []
    await truesearch.schedule_mount_check("/mnt/tank/share/child")
    assert truesearch._indexed is None
    truesearch.mount_check_timer.cancel()


def test_query_stays_in_the_dataset_of_its_path(client):
    m, svc = search_service()
    query(svc)
    assert [(request.dataset, request.share) for request in FakeClient.requests] == [("tank/data", "shares")]


def test_query_recursive_also_searches_the_child_datasets(client):
    m, svc = search_service()
    FakeClient.hits_by_dataset = {
        "tank/data": (SimpleNamespace(path="old.txt", st=stat(btime_sec=1_600_000_000)),),
        "tank/data/shares/media": (SimpleNamespace(path="new.mov", st=stat(btime_sec=1_700_000_000)),),
    }
    entries = query(svc, recursive=True)
    assert [(request.dataset, request.share) for request in FakeClient.requests] == [
        ("tank/data", "shares"),
        ("tank/data/shares/media", ""),
    ]
    # The newest entry comes first, from whichever dataset.
    assert [entry.path for entry in entries] == [
        "/mnt/tank/data/shares/media/new.mov",
        "/mnt/tank/data/shares/old.txt",
    ]
    # The limit applies to the merged results.
    assert [entry.name for entry in query(svc, recursive=True, options={"limit": 1})] == ["new.mov"]


def test_query_recursive_from_above_every_index(client):
    m, svc = search_service()
    query(svc, path="/mnt/tank", recursive=True)
    assert [(request.dataset, request.share) for request in FakeClient.requests] == [
        ("tank/data", "shares"),
        ("tank/data/shares/media", ""),
    ]


def test_query_recursive_skips_a_dataset_that_is_not_served(client):
    m, svc = search_service()
    FakeClient.errors_by_dataset = {"tank/data/shares/media": client.NoIndex("building")}
    FakeClient.hits = (SimpleNamespace(path="a.txt", st=stat()),)
    assert [entry.name for entry in query(svc, recursive=True)] == ["a.txt"]


def test_query_recursive_skips_a_dataset_the_user_cannot_reach(client):
    m, svc = search_service()
    m["filesystem.can_access_as_cred_errors"] = Mock(
        side_effect=lambda details, path, *args: ["denied"] if path.endswith("/media") else [],
    )
    query(svc, recursive=True, username="alex")
    assert [request.dataset for request in FakeClient.requests] == ["tank/data"]


def test_query_above_the_index_root_searches_the_root(client):
    m, svc = search_service()
    query(svc, path="/mnt/tank/data")
    assert (FakeClient.requests[0].share, FakeClient.requests[0].query) == ("shares", spotlight_query([]))


@pytest.mark.parametrize("path", ["/mnt/tank/data/other", "/mnt/tank/elsewhere", "/mnt/tank/off"])
def test_query_where_nothing_is_indexed_is_refused(client, path):
    m, svc = search_service()
    with pytest.raises(CallError) as e:
        query(svc, path=path)
    assert e.value.errno == errno.ENOENT
    assert FakeClient.requests == []


def test_query_as_a_user(client):
    m, svc = search_service()
    query(svc, path="/mnt/tank/data/shares/team/", username="alex")
    request = FakeClient.requests[0]
    assert (request.share, request.who.uid, request.who.gid, request.who.gids) == (
        "shares/team",
        1000,
        1001,
        (1001, 2000),
    )
    m["filesystem.can_access_as_cred_errors"].assert_called_once_with(
        USER_DETAILS,
        "/mnt/tank/data/shares/team",
        ["READ", "EXECUTE"],
        True,
        True,
    )


def test_query_as_a_user_who_cannot_reach_the_directory(client):
    m, svc = search_service()
    m["filesystem.can_access_as_cred_errors"] = Mock(return_value=["denied"])
    with pytest.raises(ValidationError):
        query(svc, username="alex")
    assert FakeClient.requests == []


@pytest.mark.parametrize(
    "path",
    [
        "/mnt/tank/data/shares/../etc",
        "/mnt/tank/data//shares",
        "/mnt/./tank",
        "mnt/tank/data",
        "/etc/passwd",
    ],
)
def test_query_refuses_a_path_outside_mnt_or_with_dot_components(client, path):
    m, svc = search_service()
    with pytest.raises(ValidationError):
        query(svc, path=path)


@pytest.mark.parametrize(
    "options",
    [
        {"limit": 0},
        {"limit": 1001},
        {"offset": 5},
        {"get": True},
        {"select": ["name"]},
        {"order_by": ["size"]},
        {"count": True},
    ],
)
def test_query_options_take_only_a_limit(options):
    with pytest.raises(ValueError):
        TruesearchQuery.model_validate({"path": "/mnt/tank/data", "query-options": options})


def test_query_refuses_a_filter_the_index_cannot_answer(client):
    m, svc = search_service()
    with pytest.raises(ValidationError) as e:
        query(svc, filters=[["name", "~", "rep.*"]])
    assert e.value.attribute == "truesearch_query.query-filters"
    assert FakeClient.requests == []


def test_query_sends_the_limit(client):
    m, svc = search_service()
    FakeClient.hits = tuple(SimpleNamespace(path=f"f{i}", st=stat(size=i)) for i in range(3))
    assert [entry.name for entry in query(svc, options={"limit": 3})] == ["f0", "f1", "f2"]
    query(svc, options={})
    assert [request.max_results for request in FakeClient.requests] == [3, 100]


@pytest.mark.parametrize(
    "refusal,code",
    [
        ("NoIndex", errno.ENOENT),
        ("Busy", errno.EBUSY),
        ("CallError", errno.EINVAL),
        ("TruesearchError", errno.ENOTCONN),
    ],
)
def test_query_refusals(client, refusal, code):
    m, svc = search_service()
    FakeClient.error = getattr(client, refusal)("detail")
    with pytest.raises(CallError) as e:
        query(svc)
    assert e.value.errno == code


# The status of both daemons in the status tests.
INDEXER_STATUS = IndexerStatus(
    index_bytes=94208,
    free_bytes=1000000,
    space_low=False,
    targets={
        "ds1": IndexerTarget(
            live=2, activity="idle", watching=True, last_full=1794142012, last_dirs=0, queued=0, size=94208
        ),
        "ds2": UnindexedTarget(why="the root is gone"),
    },
)
SERVED = {"ds1"}


def status_service(monkeypatch, indexer, served):
    """A service whose daemons give the status `indexer` and the ids `served`. An exception in either is raised."""
    m = Middleware()
    monkeypatch.setattr(
        truesearch_plugin,
        "read_config",
        lambda: [
            TargetRow(id="ds1", dataset="tank/one", root="/mnt/tank/one"),
            TargetRow(id="ds2", dataset="tank/missing", root="/mnt/tank/missing"),
            TargetRow(id="ds8", dataset="tank/disabled", root="/mnt/tank/disabled", enabled=False),
            TargetRow(id="ds9", dataset="tank/new", root="/mnt/tank/new"),
        ],
    )

    def answer(result):
        def status(timeout):
            if isinstance(result, Exception):
                raise result
            return result

        return status

    monkeypatch.setattr(truesearch_plugin, "indexer_status", answer(indexer))
    monkeypatch.setattr(truesearch_plugin, "served_ids", answer(served))
    return TrueSearchService(m)


def test_status(monkeypatch):
    svc = status_service(monkeypatch, INDEXER_STATUS, SERVED)
    status = svc.status()
    assert (status.running, status.index_bytes, status.free_bytes, status.space_low) == (True, 94208, 1000000, False)

    one, missing, new = status.datasets
    assert (one.dataset, one.path, one.state, one.served) == ("tank/one", "/mnt/tank/one", "READY", True)
    assert (one.entries, one.watching, one.index_size, one.queue_position) == (2, True, 94208, None)
    assert one.last_full_pass == datetime.fromtimestamp(1794142012, tz=timezone.utc)
    assert one.last_directory_pass is None
    assert (missing.state, missing.reason, missing.served, missing.entries) == (
        "UNAVAILABLE",
        "the root is gone",
        False,
        None,
    )
    assert (new.state, new.reason, new.served, new.entries) == ("INDEXING", None, False, None)


def test_status_with_both_daemons_down(monkeypatch):
    svc = status_service(monkeypatch, FileNotFoundError(), FileNotFoundError())
    status = svc.status()
    assert (status.running, status.index_bytes, status.space_low) == (False, None, None)
    assert [(d.state, d.served) for d in status.datasets] == [("STOPPED", False)] * 3


def test_status_of_a_draining_indexer(monkeypatch):
    # A draining indexer answers `draining`, which is not a status.
    svc = status_service(monkeypatch, ValueError("not a status: 'draining'"), SERVED)
    status = svc.status()
    assert status.running is False
    assert [d.served for d in status.datasets] == [True, False, False]


@pytest.mark.parametrize(
    "activity,state,reason",
    [
        ("idle", "READY", None),
        ("starting", "INDEXING", None),
        ("queued", "INDEXING", None),
        ("building", "INDEXING", None),
        ("full pass", "INDEXING", None),
        ("directory pass", "INDEXING", None),
        ("rebuild", "INDEXING", None),
        ("an activity of a later indexer", "INDEXING", None),
        ("waiting for its root", "UNAVAILABLE", "The dataset is not mounted at '/mnt/tank/one'."),
    ],
)
def test_each_activity_has_a_state(activity, state, reason):
    target = IndexerTarget(
        live=5,
        activity=activity,
        watching=False,
        last_full=0,
        last_dirs=0,
        queued=0,
        size=4096,
    )
    indexer = IndexerStatus(index_bytes=0, free_bytes=0, space_low=False, targets={"ds1": target})
    row = TargetRow(id="ds1", dataset="tank/one", root="/mnt/tank/one")
    status = truesearch_plugin._dataset_status(row, indexer, set())
    assert (status.state, status.reason) == (state, reason)


def test_a_row_that_the_indexer_does_not_run_is_unavailable():
    # The row is held, in conflict, or refused. The indexer gives no counts for it.
    targets = {"ds1": UnindexedTarget(why="its root is gone")}
    indexer = IndexerStatus(index_bytes=0, free_bytes=None, space_low=False, targets=targets)
    row = TargetRow(id="ds1", dataset="tank/one", root="/mnt/tank/one")
    status = truesearch_plugin._dataset_status(row, indexer, set())
    assert (status.state, status.reason, status.entries, status.index_size) == (
        "UNAVAILABLE",
        "its root is gone",
        None,
        None,
    )


@pytest.mark.parametrize(
    "path,top,result",
    [
        ("/mnt/tank/a", "/mnt/tank/a", True),
        ("/mnt/tank/a/b", "/mnt/tank/a", True),
        ("/mnt/tank/ab", "/mnt/tank/a", False),
        ("/mnt/tank", "/mnt/tank/a", False),
    ],
)
def test_beneath(path, top, result):
    assert beneath(path, top) is result


OLD = [
    TargetRow(id="ds1", dataset="gone/a", root="/mnt/gone/a"),
    TargetRow(id="ds2", dataset="gone/b", root="/mnt/gone/b", exclude=("tm",)),
    TargetRow(id="ds3", dataset="tank/c", root="/mnt/tank/c"),
    TargetRow(id="ds4", dataset="gone/d", root="/mnt/gone/d", enabled=False),
    TargetRow(id="ds5", dataset="", root="/mnt/gone/e"),
]


def test_carried_rows_keep_the_shared_rows_of_a_pool_that_is_not_imported():
    shares = {"/mnt/gone/a/team", "/mnt/gone", "/mnt/tank/c"}
    assert carried_rows(OLD, [], {"tank"}, shares) == [
        TargetRow(id="ds1", dataset="gone/a", root="/mnt/gone/a", enabled=False),
        TargetRow(id="ds2", dataset="gone/b", root="/mnt/gone/b", enabled=False),
        TargetRow(id="ds4", dataset="gone/d", root="/mnt/gone/d", enabled=False),
    ]


def test_carried_rows_leave_a_row_without_a_share():
    assert carried_rows(OLD, [], {"tank"}, {"/mnt/gone/a"}) == [
        TargetRow(id="ds1", dataset="gone/a", root="/mnt/gone/a", enabled=False),
    ]


def test_carried_rows_leave_a_row_the_datasets_hold():
    rows = [
        TargetRow(id="ds1", dataset="gone/a", root="/mnt/gone/x"),
        TargetRow(id="ds9", dataset="gone/x", root="/mnt/gone/b"),
    ]
    assert carried_rows(OLD, rows, set(), {"/mnt/gone"}) == [
        TargetRow(id="ds4", dataset="gone/d", root="/mnt/gone/d", enabled=False),
    ]
