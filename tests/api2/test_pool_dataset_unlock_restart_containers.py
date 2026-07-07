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


@pytest.mark.parametrize("running", [True, False])
def test_restart_container_on_dataset_unlock(running):
    with dataset("test", encryption_props()) as ds:
        call("pool.dataset.lock", ds, job=True)

        container = {
            "id": 1,
            "name": "test-container",
            "autostart": True,
            "dataset": ds,
            "devices": [],
            "status": {"state": "RUNNING" if running else "STOPPED"},
        }
        with mock("container.query", return_value=[container]):
            with mock("container.get_instance", return_value=container):
                ssh("rm -f /tmp/test-container-stop")
                with mock(
                    "container.stop",
                    """
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

                        if running:
                            call("filesystem.stat", "/tmp/test-container-stop")
                        else:
                            ssh("test ! -f /tmp/test-container-stop")
                        call("filesystem.stat", "/tmp/test-container-start")
