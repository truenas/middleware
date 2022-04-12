from middlewared.test.integration.utils import call, mock, pool, ssh


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


def test_system_dataset_migrate():
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
