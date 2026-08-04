import pytest

from middlewared.plugins.container.attachments import ContainerFSAttachmentDelegate
from middlewared.pytest.unit.middleware import Middleware


def fs_device(source, id_=1):
    return {"id": id_, "attributes": {"dtype": "FILESYSTEM", "source": source}}


def container(dataset, devices=None, state="STOPPED", autostart=True, id_=1, name="c"):
    return {
        "id": id_,
        "name": name,
        "dataset": dataset,
        "autostart": autostart,
        "devices": devices or [],
        "status": {"state": state},
    }


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


@pytest.mark.asyncio
async def test_container_on_paths_matches_pool_path_via_name_derived_root():
    # The root entry of `storage_paths` is derived from the dataset name, so it is a child of
    # `/mnt/<pool>`. The dataset's real mountpoint is `/mnt/.truenas_containers/<pool>/...`, which
    # is not -- switching to it would silently stop matching containers on pool export and lock.
    m = Middleware()
    m["filesystem.is_child"] = lambda child, parent: any(
        c == p or c.startswith(f"{p}/") for c in child for p in parent
    )
    delegate = ContainerFSAttachmentDelegate(m)
    c = container("tank/.truenas_containers/containers/c")

    assert await delegate.container_on_paths(c, ["/mnt/tank"]) is True


class StopJob:
    async def wait(self, raise_error=False):
        pass


class StartDriver:
    """Drives the autostart start paths and `delete` against a single container, recording actions."""

    def __init__(self, state, devices=None, locked_paths=(), autostart=True):
        self.actions = []
        self.container = container("tank/ds", devices, state=state, autostart=autostart)
        self.middleware = Middleware()
        self.middleware["filesystem.is_child"] = lambda child, parent: True
        self.middleware["pool.dataset.path_in_locked_datasets"] = lambda path: path in locked_paths
        self.middleware["container.query"] = self._query
        self.middleware["container.get_instance"] = lambda *args: self.container
        self.middleware["container.start"] = self._record("start")
        self.middleware["container.stop"] = self._record("stop", StopJob())
        self.middleware["container.delete_container_from_libvirt"] = self._record("teardown")
        self.middleware["container.delete_container_from_db"] = self._record("remove")
        self.delegate = ContainerFSAttachmentDelegate(self.middleware)

    def _query(self, filters=None, *args):
        # Honor the `autostart` filter the autostart-aware start paths pass down
        if filters and ("autostart", "=", True) in filters and not self.container["autostart"]:
            return []
        return [self.container]

    def _record(self, action, result=None):
        def record(*args):
            self.actions.append(action)
            return result

        return record

    async def run_import(self):
        await self.delegate.start_on_import("/mnt/tank")
        return self.actions

    async def run_delete(self):
        await self.delegate.delete([{"id": self.container["id"], "name": self.container["name"]}])
        return self.actions


@pytest.mark.asyncio
async def test_start_on_import_starts_autostart_container():
    assert await StartDriver("STOPPED").run_import() == ["start"]


@pytest.mark.asyncio
async def test_start_on_import_skips_non_autostart_container():
    # A pool being re-imported must not boot containers the user never asked to autostart
    assert await StartDriver("STOPPED", autostart=False).run_import() == []


@pytest.mark.asyncio
async def test_delete_tears_down_the_domain_without_removing_records():
    # The container's database row is the only copy of its definition and its rootfs dataset
    # outlives the delegate, so `delete` must never remove records. It must go through the libvirt
    # teardown rather than `stop`: our caller destroys the storage as soon as this returns, and
    # `stop` comes back while the container's runtime mounts are still pinning it.
    assert await StartDriver("RUNNING").run_delete() == ["teardown"]


@pytest.mark.asyncio
async def test_delete_of_bind_mount_source_keeps_the_container():
    # Deleting a dataset a container merely bind-mounts reaches the delegate through `query`, and
    # must cost the user the mount, not the whole container.
    driver = StartDriver("RUNNING", devices=[fs_device("/mnt/tank/media")])
    attachments = await driver.delegate.query("/mnt/tank/media", True)
    assert attachments == [{"id": 1, "name": "c"}]

    await driver.delegate.delete(attachments)
    assert driver.actions == ["teardown"]


class DestroyDriver:
    """Drives `destroy` against a set of containers, recording every (action, container name)."""

    def __init__(self, containers, failing_db_removal=()):
        self.actions = []
        self.etc_generated = []
        self.containers = containers
        self.failing_db_removal = failing_db_removal
        self.middleware = Middleware()
        self.middleware["etc.generate"] = self.etc_generated.append
        self.middleware["container.query"] = lambda *args: list(containers)
        self.middleware["container.delete_container_from_libvirt"] = self._record("teardown")
        self.middleware["container.delete_container_from_db"] = self._record("remove", self.failing_db_removal)
        self.delegate = ContainerFSAttachmentDelegate(self.middleware)

    def _record(self, action, failing=()):
        def record(container):
            self.actions.append((action, container["name"]))
            if container["name"] in failing:
                raise Exception(f"{container['name']} blew up")

        return record

    async def run(self, path="/mnt/tank"):
        await self.delegate.destroy(path)
        return self.actions


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["STOPPED", "RUNNING"])
async def test_destroy_removes_records_whatever_the_runtime_state(state):
    # Runtime state must not decide this: `query` only reports active containers, so a cleanup keyed
    # off it would drop the records of running containers and keep those of stopped ones.
    driver = DestroyDriver([container("tank/.truenas_containers/containers/c", state=state)])
    assert await driver.run() == [("teardown", "c"), ("remove", "c")]
    assert driver.etc_generated == ["libvirt_guests"]


@pytest.mark.asyncio
async def test_destroy_keeps_container_rooted_on_another_pool():
    # The container merely bind-mounts the destroyed pool; its rootfs is intact on `other`, and its
    # record is the only thing pointing at it.
    driver = DestroyDriver(
        [container("other/.truenas_containers/containers/c", devices=[fs_device("/mnt/tank/media")])]
    )
    assert await driver.run() == []
    assert driver.etc_generated == []


@pytest.mark.asyncio
async def test_destroy_removes_container_rooted_outside_the_container_dataset():
    # A legacy container migration may leave the rootfs outside `.truenas_containers`; it is still on
    # the destroyed pool, so matching on the pool name rather than on that prefix is what catches it.
    driver = DestroyDriver([container("tank/.ix-virt/containers/legacy", name="legacy")])
    assert await driver.run() == [("teardown", "legacy"), ("remove", "legacy")]


@pytest.mark.asyncio
async def test_destroy_does_not_match_a_pool_whose_name_shares_a_prefix():
    driver = DestroyDriver([
        container("tank/.truenas_containers/containers/a", id_=1, name="a"),
        container("tank2/.truenas_containers/containers/b", id_=2, name="b"),
    ])
    assert await driver.run() == [("teardown", "a"), ("remove", "a")]


@pytest.mark.asyncio
async def test_destroy_isolates_per_container_failures():
    # One container failing must not leave the rest of the pool's records behind
    driver = DestroyDriver(
        [
            container("tank/.truenas_containers/containers/a", id_=1, name="a"),
            container("tank/.truenas_containers/containers/b", id_=2, name="b"),
        ],
        failing_db_removal=("a",),
    )
    assert await driver.run() == [("teardown", "a"), ("remove", "a"), ("teardown", "b"), ("remove", "b")]
    assert driver.etc_generated == ["libvirt_guests"]


@pytest.mark.asyncio
async def test_destroy_skips_etc_generate_when_nothing_was_removed():
    driver = DestroyDriver([container("other/.truenas_containers/containers/c")])
    await driver.run()
    assert driver.etc_generated == []
