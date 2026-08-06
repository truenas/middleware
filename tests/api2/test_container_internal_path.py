import pytest

from middlewared.test.integration.assets.container import (
    ALPINE_IMAGE_NAME,
    configure_bridge,
    container,
    resolve_image,
)
from middlewared.test.integration.utils import call, pool, ssh

CONTAINER_DS = f"{pool}/.truenas_containers"


@pytest.fixture(scope="module", autouse=True)
def bridge():
    configure_bridge()


@pytest.fixture(scope="module")
def image():
    yield resolve_image(ALPINE_IMAGE_NAME)


@pytest.fixture(scope="module")
def alpine_container(image):
    with container(image) as c:
        yield c


def image_snapshot():
    # The tree is hidden from the API now, so go around it.
    out = ssh(f"zfs list -H -o name -t snapshot -r {CONTAINER_DS}/images")
    return next(line for line in out.splitlines() if line.endswith("@image"))


def test_container_dataset_hidden_from_zfs_resource_query(alpine_container):
    names = [r["name"] for r in call("zfs.resource.query", {"paths": [pool], "get_children": True})]

    assert CONTAINER_DS not in names
    assert not [name for name in names if name.startswith(f"{CONTAINER_DS}/")]


def test_container_dataset_still_visible_when_named_explicitly(alpine_container):
    """Naming an internal path opts out of the filter.

    The mountpoint repair depends on this, so it has to keep working.
    """
    rv = call("zfs.resource.query", {"paths": [CONTAINER_DS], "properties": ["mountpoint"]})

    assert len(rv) == 1
    assert rv[0]["properties"]["mountpoint"]["value"] == f"/mnt/.truenas_containers/{pool}"


@pytest.mark.parametrize("suffix", ["", "/containers", "/images"])
def test_zfs_resource_destroy_refused(alpine_container, suffix):
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": f"{CONTAINER_DS}{suffix}", "recursive": True})

    assert "protected" in str(exc_info.value).lower(), exc_info.value


def test_zfs_resource_destroy_of_container_rootfs_refused(alpine_container):
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": alpine_container["dataset"], "recursive": True})

    assert "protected" in str(exc_info.value).lower(), exc_info.value


@pytest.mark.parametrize("suffix", ["", "/containers"])
def test_pool_dataset_delete_refused(alpine_container, suffix):
    with pytest.raises(Exception) as exc_info:
        call("pool.dataset.delete", f"{CONTAINER_DS}{suffix}", {"recursive": True})

    assert "invalid location" in str(exc_info.value).lower(), exc_info.value


def test_image_snapshot_delete_refused(alpine_container):
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.snapshot.destroy", {"path": image_snapshot()})

    assert "protected" in str(exc_info.value).lower(), exc_info.value


def test_image_snapshot_delete_with_defer_refused(alpine_container):
    """`defer` skips the dependent-clone check, so before the guard this one succeeded.

    Every container rootfs is a clone of this snapshot, which is what made the
    non-deferred destroy fail with EBUSY rather than because it was protected.
    """
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.snapshot.destroy", {"path": image_snapshot(), "defer": True})

    assert "protected" in str(exc_info.value).lower(), exc_info.value


def test_pool_snapshot_delete_refused(alpine_container):
    with pytest.raises(Exception) as exc_info:
        call("pool.snapshot.delete", image_snapshot())

    assert "protected" in str(exc_info.value).lower(), exc_info.value


def test_container_lifecycle_still_works(image):
    """The plugin destroys its own datasets and snapshots with `bypass`.

    If any of those lost their bypass, create/delete would start failing with EACCES.
    """
    with container(image, name="protected") as c:
        assert call("container.get_instance", c["id"])["dataset"].startswith(f"{CONTAINER_DS}/")
