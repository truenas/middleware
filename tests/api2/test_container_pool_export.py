import pytest

from middlewared.test.integration.assets.container import (
    ALPINE_IMAGE_NAME,
    configure_bridge,
    container,
    filesystem_device,
    resolve_image,
)
from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.utils import call, ssh

# Every test here runs against a throwaway pool so that exporting/destroying it can never
# touch a pool the system actually depends on.
POOL_NAME = "test_container_export"


@pytest.fixture(scope="module", autouse=True)
def bridge():
    configure_bridge()


@pytest.fixture(scope="module")
def image():
    yield resolve_image(ALPINE_IMAGE_NAME)


def container_exists(id_):
    return bool(call("container.query", [["id", "=", id_]]))


def test_cascade_export_keeps_container_records(image):
    """A cascaded export of a pool that is not destroyed must not drop container records.

    The rootfs datasets go with the pool and are still there, so removing the records
    would orphan live storage with no way to get it back -- the container's definition
    and its idmap slice exist nowhere else.
    """
    with another_pool({"name": POOL_NAME}) as pool:
        with container(image, options={"pool": POOL_NAME}, start=True) as c:
            call("pool.export", pool["id"], {"cascade": True, "destroy": False}, job=True)

            assert container_exists(c["id"]), "cascaded export destroyed the container's records"

            call("pool.import_pool", {"guid": pool["guid"], "name": POOL_NAME}, job=True)

            # The record still points at storage that is really there, so it runs again
            assert call("container.get_instance", c["id"])["dataset"] == c["dataset"]
            call("container.start", c["id"])
            assert call("container.get_instance", c["id"])["status"]["state"] == "RUNNING"


def test_cascade_destroy_removes_container_records(image):
    """Destroying the pool as well is the one case where the records are safe to drop.

    Both a running and a stopped container are checked: the delegate only ever saw
    active containers, which made the old cleanup drop the records of running
    containers and keep those of stopped ones.
    """
    with another_pool({"name": POOL_NAME}) as pool:
        with (
            container(image, options={"pool": POOL_NAME}, name="running", start=True) as running,
            container(image, options={"pool": POOL_NAME}, name="stopped") as stopped,
        ):
            call("pool.export", pool["id"], {"cascade": True, "destroy": True}, job=True)

            assert not container_exists(running["id"])
            assert not container_exists(stopped["id"]), "records of stopped containers survived a cascaded destroy"


def test_destroy_without_cascade_keeps_container_records(image):
    """`cascade=False` means the user asked to keep their attachment configuration.

    The pool having been destroyed does not override that, so the records survive even
    though their storage is gone -- the user is left to delete the containers themselves.
    """
    with another_pool({"name": POOL_NAME}) as pool:
        with container(image, options={"pool": POOL_NAME}) as c:
            call("pool.export", pool["id"], {"cascade": False, "destroy": True}, job=True)

            assert container_exists(c["id"]), "a non-cascaded export discarded container records"


def test_cascade_destroy_of_offline_pool_keeps_container_records(image):
    """Destroying an OFFLINE pool destroys nothing, so the records must stay.

    An OFFLINE pool is not imported, so `pool.export` skips both the zpool destroy and
    the disk wipe and the container's rootfs survives untouched. Keying the cleanup off
    the requested `destroy` option instead of what actually happened would orphan that
    storage -- the exact failure this whole change exists to prevent.
    """
    with another_pool({"name": POOL_NAME}) as pool:
        with container(image, options={"pool": POOL_NAME}) as c:
            try:
                ssh(f"zpool export {POOL_NAME}")
                assert call("pool.get_instance", pool["id"])["status"] == "OFFLINE"

                call(
                    "pool.export",
                    pool["id"],
                    {"cascade": True, "destroy": True},
                    job=True,
                )

                assert container_exists(c["id"]), "records were dropped for a pool that was never actually destroyed"
            finally:
                # Bring the pool back so the container and the pool tear down normally.
                if any(p["guid"] == pool["guid"] for p in call("pool.import_find", job=True)):
                    call(
                        "pool.import_pool",
                        {"guid": pool["guid"], "name": POOL_NAME},
                        job=True,
                    )


def test_dataset_delete_of_bind_mount_source_keeps_container(image):
    """Deleting a bind-mounted dataset costs the container the mount, not its definition.

    `pool.dataset.delete` has no cascade flag, so it can only ever take the conservative
    action.
    """
    with another_pool({"name": POOL_NAME}):
        with dataset("media", pool=POOL_NAME) as media:
            with container(image, options={"pool": POOL_NAME}) as c:
                with filesystem_device(c["id"], f"/mnt/{media}", "/data"):
                    call("container.start", c["id"])
                    instance = call("container.get_instance", c["id"])
                    assert instance["status"]["state"] == "RUNNING"

                    call("pool.dataset.delete", media, {"recursive": True})

                    assert container_exists(c["id"]), "deleting a bind-mount source deleted the container"
                    instance = call("container.get_instance", c["id"])
                    assert instance["status"]["state"] == "STOPPED"


def test_container_storage_remapped_after_pool_rename(image):
    """A pool imported under a new name leaves container records pointing at the old one.

    The dataset is always `<pool>/.truenas_containers/containers/<name>`, so the new
    location is derived rather than guessed, and the container is usable again after the
    import.
    """
    renamed = f"{POOL_NAME}_renamed"
    with another_pool({"name": POOL_NAME}) as pool:
        with container(image, options={"pool": POOL_NAME}) as c:
            assert c["dataset"].startswith(f"{POOL_NAME}/")

            call(
                "pool.export",
                pool["id"],
                {"cascade": False, "destroy": False},
                job=True,
            )
            call("pool.import_pool", {"guid": pool["guid"], "name": renamed}, job=True)

            # `another_pool` tears down by guid, so it finds the renamed pool on its own.
            remapped = call("container.get_instance", c["id"])["dataset"]
            assert remapped == c["dataset"].replace(POOL_NAME, renamed, 1), (
                f"container was left pointing at the old pool: {remapped}"
            )

            call("container.start", c["id"])
            assert call("container.get_instance", c["id"])["status"]["state"] == "RUNNING"
            call("container.stop", c["id"], {"force": True}, job=True)
