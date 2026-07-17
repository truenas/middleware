import pytest

from assets.unlock_restart import (
    assert_started_only_after_all_deps_unlocked,
    encryption_props,
    marker_mock,
    model_mock,
    unlock,
)
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, mock, ssh


def container_entry(dataset_name, state, sources=()):
    # A single line of Python building a `ContainerEntry`, to be evaluated by `model_mock`.
    devices = ", ".join(
        f"ContainerDeviceEntry.model_construct(id={i}, container=1, attributes="
        f"ContainerFilesystemDevice.model_construct("
        f'dtype="FILESYSTEM", source={source!r}, target="/data"))'
        for i, source in enumerate(sources, start=1)
    )
    return (
        f'ContainerEntry.model_construct(id=1, name="test-container", autostart=True, '
        f"dataset={dataset_name!r}, devices=[{devices}], "
        f"status=ContainerStatus.model_construct(state={state!r}))"
    )


@pytest.mark.parametrize("state", ["RUNNING", "STOPPED", "SUSPENDED"])
def test_restart_container_on_dataset_unlock(state):
    with dataset("test", encryption_props()) as ds:
        call("pool.dataset.lock", ds, job=True)

        entry = container_entry(ds, state)
        with (
            mock("container.query", declaration=model_mock(f"[{entry}]")),
            mock("container.get_instance", declaration=model_mock(entry)),
            mock("container.stop", declaration=marker_mock("/tmp/test-container-stop")),
            mock(
                "container.start", declaration=marker_mock("/tmp/test-container-start")
            ),
        ):
            ssh("rm -f /tmp/test-container-stop /tmp/test-container-start")
            unlock(ds)

            # A RUNNING container is bounced (stopped then started) so it picks up the freshly
            # mounted storage; a STOPPED one is just started; a SUSPENDED one is left paused.
            if state == "RUNNING":
                call("filesystem.stat", "/tmp/test-container-stop")
            else:
                ssh("test ! -f /tmp/test-container-stop")

            if state == "SUSPENDED":
                ssh("test ! -f /tmp/test-container-start")
            else:
                call("filesystem.stat", "/tmp/test-container-start")


def test_container_not_started_until_all_encrypted_storage_unlocked():
    # A container rooted on one encrypted dataset that also bind-mounts a second, independently
    # encrypted dataset must not be started until BOTH are unlocked -- starting it with the
    # still-locked bind-mount source would bring it up with a missing/empty filesystem.
    with (
        dataset("croot", encryption_props()) as root_ds,
        dataset("cdata", encryption_props()) as data_ds,
    ):
        call("pool.dataset.lock", root_ds, job=True)
        call("pool.dataset.lock", data_ds, job=True)

        entry = container_entry(root_ds, "STOPPED", sources=[f"/mnt/{data_ds}"])
        with (
            mock("container.query", declaration=model_mock(f"[{entry}]")),
            mock("container.get_instance", declaration=model_mock(entry)),
            mock(
                "container.start", declaration=marker_mock("/tmp/split-container-start")
            ),
        ):
            assert_started_only_after_all_deps_unlocked(
                "/tmp/split-container-start", root_ds, data_ds
            )
