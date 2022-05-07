import pytest
from pytest_dependency import depends

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, mock, pool, ssh

from auto_config import dev_test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


def read_log():
    return ssh("cat /var/log/middlewared.log")


def write_to_log(string):
    assert string not in read_log()

    with mock("test.test1", f"""
        from middlewared.service import lock

        async def mock(self, *args):
            self.logger.debug({string!r})
    """):
        call("test.test1")

    assert string in read_log()


def test_system_dataset_migrate(request):
    depends(request, ["pool_04"], scope="session")

    config = call("systemdataset.config")
    assert config["pool"] == pool
    assert config["syslog"]

    # Make sure that log files are synced to the new location
    write_to_log("test_system_dataset_migrate step 1")

    call("systemdataset.update", {"pool": "boot-pool"}, job=True)
    assert "test_system_dataset_migrate step 1" in read_log()

    write_to_log("test_system_dataset_migrate step 2")

    call("systemdataset.update", {"pool": pool}, job=True)
    assert "test_system_dataset_migrate step 1" in read_log()
    assert "test_system_dataset_migrate step 2" in read_log()


@pytest.mark.parametrize("lock", [False, True])
def test_migrate_to_a_pool_with_passphrase_encrypted_root_dataset(request, lock):
    depends(request, ["pool_04"], scope="session")

    config = call("systemdataset.config")
    assert config["pool"] == pool

    with another_pool({"encryption": True, "encryption_options": {"passphrase": "passphrase"}}):
        if lock:
            call("pool.dataset.lock", "test", job=True)

        assert "test" in call("systemdataset.pool_choices")

        call("systemdataset.update", {"pool": "test"}, job=True)

        ds = call("zfs.dataset.get_instance", "test/.system")
        assert ds["properties"]["encryption"]["value"] == "off"

        call("systemdataset.update", {"pool": pool}, job=True)
