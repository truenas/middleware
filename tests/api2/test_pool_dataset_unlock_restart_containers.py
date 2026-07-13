import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, mock, ssh


PASSPHRASE = "12345678"


def encryption_props():
    return {
        "encryption_options": {"generate_key": False, "passphrase": PASSPHRASE},
        "encryption": True,
        "inherit_encryption": False,
    }


@pytest.mark.parametrize("state", ["RUNNING", "STOPPED", "SUSPENDED"])
def test_restart_container_on_dataset_unlock(state):
    with dataset("test", encryption_props()) as ds:
        call("pool.dataset.lock", ds, job=True)

        container = {
            "id": 1,
            "name": "test-container",
            "autostart": True,
            "dataset": ds,
            "devices": [],
            "status": {"state": state},
        }
        with (
            mock("container.query", return_value=[container]),
            mock("container.get_instance", return_value=container),
        ):
            ssh("rm -f /tmp/test-container-stop")
            with mock(
                "container.stop",
                declaration="""
                from middlewared.service import job

                @job()
                def mock(self, job, *args):
                    with open("/tmp/test-container-stop", "w") as f:
                        pass
                """,
            ):
                ssh("rm -f /tmp/test-container-start")
                with mock(
                    "container.start",
                    declaration="""
                    def mock(self, *args):
                        with open("/tmp/test-container-start", "w") as f:
                            pass
                    """,
                ):
                    call(
                        "pool.dataset.unlock",
                        ds,
                        {"datasets": [{"name": ds, "passphrase": PASSPHRASE}]},
                        job=True,
                    )

                    # A RUNNING container is bounced (stopped then started) so it picks up the
                    # freshly-mounted storage; a STOPPED one is just started; a SUSPENDED one is
                    # left paused -- neither stopped nor started.
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

        container = {
            "id": 1,
            "name": "split-container",
            "autostart": True,
            "dataset": root_ds,
            "devices": [
                {"attributes": {"dtype": "FILESYSTEM", "source": f"/mnt/{data_ds}"}}
            ],
            "status": {"state": "STOPPED"},
        }
        with (
            mock("container.query", return_value=[container]),
            mock("container.get_instance", return_value=container),
            mock(
                "container.start",
                declaration="""
                def mock(self, *args):
                    with open("/tmp/split-container-start", "w") as f:
                        pass
                """,
            ),
        ):
            ssh("rm -f /tmp/split-container-start")

            # Unlock only the root dataset: the bind-mount source is still locked, so the
            # container must NOT be started yet.
            call(
                "pool.dataset.unlock",
                root_ds,
                {"datasets": [{"name": root_ds, "passphrase": PASSPHRASE}]},
                job=True,
            )
            ssh("test ! -f /tmp/split-container-start")

            # Unlock the bind-mount source: now all of the container's storage is
            # available, so it is started.
            call(
                "pool.dataset.unlock",
                data_ds,
                {"datasets": [{"name": data_ds, "passphrase": PASSPHRASE}]},
                job=True,
            )
            call("filesystem.stat", "/tmp/split-container-start")
