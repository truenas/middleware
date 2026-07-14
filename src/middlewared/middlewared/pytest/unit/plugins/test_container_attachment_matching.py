import pytest

from middlewared.api.current import (
    ContainerDeviceEntry,
    ContainerEntry,
    ContainerFilesystemDevice,
    ContainerNICDevice,
    ContainerStatus,
)
from middlewared.plugins.container.attachments import ContainerFSAttachmentDelegate
from middlewared.pytest.unit.middleware import Middleware


def fs_device(source):
    return ContainerDeviceEntry.model_construct(
        id=1,
        container=1,
        attributes=ContainerFilesystemDevice.model_construct(dtype="FILESYSTEM", source=source, target="/data"),
    )


def nic_device():
    return ContainerDeviceEntry.model_construct(
        id=2, container=1, attributes=ContainerNICDevice.model_construct(dtype="NIC")
    )


def container(dataset, devices=None, state="STOPPED"):
    return ContainerEntry.model_construct(
        id=1,
        name="c",
        dataset=dataset,
        autostart=True,
        devices=devices or [],
        status=ContainerStatus.model_construct(state=state),
    )


def test_storage_paths_gathers_root_and_filesystem_sources():
    delegate = ContainerFSAttachmentDelegate(Middleware())
    c = container(
        "tank/.truenas_containers/containers/c",
        [
            fs_device("/mnt/tank/data"),
            nic_device(),  # not storage, ignored
            fs_device("/mnt/other/data2"),
        ],
    )
    assert delegate.storage_paths(c) == [
        "/mnt/tank/.truenas_containers/containers/c",
        "/mnt/tank/data",
        "/mnt/other/data2",
    ]


@pytest.mark.asyncio
async def test_container_on_paths_matches_in_a_single_is_child_call():
    m = Middleware()
    calls = []

    def fake_is_child(child, parent):
        calls.append((child, parent))
        return True

    m["filesystem.is_child"] = fake_is_child
    delegate = ContainerFSAttachmentDelegate(m)
    c = container("tank/.truenas_containers/containers/c", [fs_device("/mnt/tank/data")])

    assert await delegate.container_on_paths(c, {"/mnt/tank"}) is True
    # One call, with the root dataset + every FILESYSTEM source and the unlocked paths as lists
    assert calls == [(["/mnt/tank/.truenas_containers/containers/c", "/mnt/tank/data"], ["/mnt/tank"])]


@pytest.mark.asyncio
async def test_storage_locked_considers_root_and_filesystem_sources():
    m = Middleware()
    locked = set()
    m["pool.dataset.path_in_locked_datasets"] = lambda path: path in locked
    delegate = ContainerFSAttachmentDelegate(m)
    c = container("tank/.truenas_containers/containers/c", [fs_device("/mnt/other/data")])

    assert await delegate.storage_locked(c) is False

    # A still-locked bind-mount source defers the start
    locked.add("/mnt/other/data")
    assert await delegate.storage_locked(c) is True


class StopJob:
    async def wait(self, *args, **kwargs):
        return None


class StartOnUnlockDriver:
    """Drives `start_on_unlock` against a single autostart container, recording the actions taken."""

    def __init__(self, state, devices=None, locked_paths=()):
        self.actions: list[str] = []
        self.container = container("tank/ds", devices, state=state)
        self.middleware = Middleware()
        self.middleware["filesystem.is_child"] = lambda child, parent: True
        self.middleware["pool.dataset.path_in_locked_datasets"] = lambda path: path in locked_paths
        self.middleware.services.container.query = lambda *args: [self.container]
        self.middleware.services.container.get_instance = lambda *args: self.container
        self.middleware.services.container.start = self._record("start")
        self.middleware.services.container.stop = self._record("stop")
        self.delegate = ContainerFSAttachmentDelegate(self.middleware)

    def _record(self, action):
        def record(*args):
            self.actions.append(action)
            return StopJob()

        return record

    async def run(self):
        await self.delegate.start_on_unlock([({"name": "tank/ds", "type": "FILESYSTEM"}, "/mnt/tank/ds")])
        return self.actions


@pytest.mark.asyncio
async def test_start_on_unlock_starts_stopped_container():
    assert await StartOnUnlockDriver("STOPPED").run() == ["start"]


@pytest.mark.asyncio
async def test_start_on_unlock_bounces_running_container():
    # A running container is stopped first so it comes back up on the freshly mounted storage
    assert await StartOnUnlockDriver("RUNNING").run() == ["stop", "start"]


@pytest.mark.asyncio
async def test_start_on_unlock_leaves_suspended_container_paused():
    assert await StartOnUnlockDriver("SUSPENDED").run() == []


@pytest.mark.asyncio
async def test_start_on_unlock_defers_while_bind_mount_source_is_locked():
    # The container also bind-mounts a second, independently encrypted dataset: starting it before
    # that one is unlocked would bring it up with a missing/empty filesystem.
    assert (
        await StartOnUnlockDriver(
            "STOPPED", devices=[fs_device("/mnt/other/data")], locked_paths=("/mnt/other/data",)
        ).run()
        == []
    )


@pytest.mark.asyncio
async def test_start_on_unlock_skips_zvol_only_unlock():
    # A zvol has no filesystem to bind-mount or root a container on
    driver = StartOnUnlockDriver("STOPPED")
    await driver.delegate.start_on_unlock([({"name": "tank/vol", "type": "VOLUME"}, "/mnt/tank/vol")])
    assert driver.actions == []
