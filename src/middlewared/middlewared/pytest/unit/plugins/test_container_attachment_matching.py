import pytest

from middlewared.plugins.container.attachments import ContainerFSAttachmentDelegate
from middlewared.pytest.unit.middleware import Middleware


def fs_device(source):
    return {"attributes": {"dtype": "FILESYSTEM", "source": source}}


def container(dataset, devices=None):
    return {"id": 1, "name": "c", "dataset": dataset, "devices": devices or []}


def test_storage_paths_gathers_root_and_filesystem_sources():
    delegate = ContainerFSAttachmentDelegate(Middleware())
    c = container(
        "tank/.truenas_containers/containers/c",
        [
            fs_device("/mnt/tank/data"),
            {"attributes": {"dtype": "NIC"}},  # not storage, ignored
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
