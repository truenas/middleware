import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, mock, ssh


PASSPHRASE = "12345678"
pytestmark = [pytest.mark.vm, pytest.mark.zfs]


def encryption_props():
    return {
        "encryption_options": {"generate_key": False, "passphrase": PASSPHRASE},
        "encryption": True,
        "inherit_encryption": False
    }


@pytest.mark.parametrize("zvol", [True, False])
def test_restart_vm_on_dataset_unlock(zvol):
    if zvol:
        data = {"type": "VOLUME", "volsize": 1048576}
    else:
        data = {}

    with dataset("test", {**data, **encryption_props()}) as ds:
        call("pool.dataset.lock", ds, job=True)

        if zvol:
            device = {"dtype": "DISK", "attributes": {"path": f"/dev/zvol/{ds}"}}
        else:
            device = {"dtype": "RAW", "attributes": {"path": f"/mnt/{ds}/child"}}

        with mock("vm.query", return_value=[{"id": 1, "devices": [device]}]):
            with mock("vm.status", return_value={"state": "RUNNING"}):
                ssh("rm -f /tmp/test-vm-stop")
                with mock("vm.stop", """
                    from middlewared.service import job

                    @job()
                    def mock(self, job, *args):
                        with open("/tmp/test-vm-stop", "w") as f:
                            pass
                """):
                    ssh("rm -f /tmp/test-vm-start")
                    with mock("vm.start", declaration="""
                        def mock(self, job, *args):
                            with open("/tmp/test-vm-start", "w") as f:
                                pass
                    """):
                        call(
                            "pool.dataset.unlock",
                            ds,
                            {"datasets": [{"name": ds, "passphrase": PASSPHRASE}]},
                            job=True,
                        )

                        call("filesystem.stat", "/tmp/test-vm-stop")
                        call("filesystem.stat", "/tmp/test-vm-start")
