import pytest

from middlewared.test.integration.assets.container import (
    ALPINE_IMAGE_NAME,
    configure_bridge,
    container,
    resolve_image,
)
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, mock, ssh

# A throwaway pool, so exporting and reimporting it can never touch a pool the system needs.
POOL_NAME = "test_container_mnt"
CONTAINER_DS = f"{POOL_NAME}/.truenas_containers"
EXPECTED_MOUNTPOINT = f"/mnt/.truenas_containers/{POOL_NAME}"


@pytest.fixture(scope="module", autouse=True)
def bridge():
    configure_bridge()


@pytest.fixture(scope="module")
def image():
    yield resolve_image(ALPINE_IMAGE_NAME)


def mountpoint():
    return ssh(f"zfs get -H -o value mountpoint {CONTAINER_DS}").strip()


def test_import_repairs_drifted_container_mountpoint(image):
    """The container dataset is an internal path, so pool import cannot see it in the
    first-level query any more. It has to be repaired by name instead, and this is the
    regression test for that: without the repair the container comes back mounted under
    the pool's own tree and starts on an empty directory.
    """
    with another_pool({"name": POOL_NAME}) as pool:
        with container(image, options={"pool": POOL_NAME}) as c:
            assert mountpoint() == EXPECTED_MOUNTPOINT

            # What a foreign pool, or `zfs inherit -r mountpoint`, leaves behind.
            ssh(f"zfs inherit -r mountpoint {POOL_NAME}")
            assert mountpoint() == f"/mnt/{POOL_NAME}/.truenas_containers"

            call("pool.export", pool["id"], {"cascade": True, "destroy": False}, job=True)
            call("pool.import_pool", {"guid": pool["guid"], "name": POOL_NAME}, job=True)

            assert mountpoint() == EXPECTED_MOUNTPOINT

            call("container.start", c["id"])
            assert call("container.get_instance", c["id"])["status"]["state"] == "RUNNING"
            call("container.stop", c["id"], {"force": True}, job=True)


def test_import_does_not_touch_correct_container_mountpoint(image):
    """A healthy pool must not have any mountpoint rewritten on import."""
    with another_pool({"name": POOL_NAME}) as pool:
        with container(image, options={"pool": POOL_NAME}):
            call("pool.export", pool["id"], {"cascade": True, "destroy": False}, job=True)

            with mock(
                "pool.dataset.update_impl",
                """
                async def mock(self, *args):
                    raise Exception("mountpoint was reset on a healthy pool")
            """,
            ):
                call("pool.import_pool", {"guid": pool["guid"], "name": POOL_NAME}, job=True)

            assert mountpoint() == EXPECTED_MOUNTPOINT


def test_ensure_datasets_repairs_instead_of_raising(image):
    """A drifted mountpoint used to be a hard `CallError` with no way forward."""
    with another_pool({"name": POOL_NAME}):
        with container(image, options={"pool": POOL_NAME}, name="first"):
            ssh(f"zfs set mountpoint=/{POOL_NAME}/.truenas_containers {CONTAINER_DS}")
            assert mountpoint() != EXPECTED_MOUNTPOINT

            # `container.create` calls `container.ensure_datasets`, which used to raise here.
            with container(image, options={"pool": POOL_NAME}, name="second"):
                assert mountpoint() == EXPECTED_MOUNTPOINT
