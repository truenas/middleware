import pytest

from truenas_api_client import ClientException

from middlewared.test.integration.assets.pool import another_pool, pool as pool_name
from middlewared.test.integration.utils import call, disable_failover, mock


def test_systemdataset_migrate_error():
    """
    On HA this test will fail with the error below if failover is enabled:
    [ENOTSUP] Disable failover before exporting last pool on system.
    """
    with disable_failover():
        pool = call("pool.query", [["name", "=", pool_name]], {"get": True})

        with mock("systemdataset.update", """\
            from middlewared.service import job, CallError

            @job()
            def mock(self, job, *args):
                raise CallError("Test error")
        """):
            with pytest.raises(ClientException) as e:
                call("pool.export", pool["id"], job=True)

            assert e.value.error == (
                "[EFAULT] This pool contains system dataset, but its reconfiguration failed: [EFAULT] Test error"
            )


def test_destroy_offline_disks():
    with another_pool(topology=(2, lambda disks: {
        "data": [
            {"type": "MIRROR", "disks": disks[0:2]},
        ],
    })) as pool:
        disk = pool["topology"]["data"][0]["children"][0]

        call("pool.offline", pool["id"], {"label": disk["guid"]})

        call("pool.export", pool["id"], {"destroy": True}, job=True)

        unused = [unused for unused in call("disk.get_unused") if unused["name"] == disk["disk"]][0]

        assert unused["exported_zpool"] is None
