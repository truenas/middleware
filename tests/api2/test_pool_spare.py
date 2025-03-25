import pytest

from truenas_api_client import ValidationErrors
from middlewared.test.integration.assets.disk import fake_disks
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call


def test_pool_create_too_small_spare():
    disk = call("disk.get_unused")[0]["name"]

    with fake_disks({"sdz": {"size_bytes": 1024 * 1024 * 1024}}):
        with pytest.raises(ValidationErrors) as ve:
            pool = call("pool.create", {
                "name": "test",
                "encryption": False,
                "allow_duplicate_serials": True,
                "topology": {
                    "data": [
                        {"type": "STRIPE", "disks": [disk]},
                    ],
                    "spares": ["sdz"],
                },
            }, job=True)
            call("pool.export", pool["id"], job=True)

        assert ve.value.errors[0].errmsg.startswith("Spare sdz (1 GiB) is smaller than the smallest data disk")


def test_pool_update_spare():
    with another_pool() as pool:
        # Test too small
        with fake_disks({"sdz": {"size_bytes": 1024 * 1024 * 1024}}):
            with pytest.raises(ValidationErrors) as ve:
                call("pool.update", pool["id"], {
                    "topology": {
                        "spares": ["sdz"],
                    },
                }, job=True)

            assert ve.value.errors[0].errmsg.startswith("Spare sdz (1 GiB) is smaller than the smallest data disk")

        # Test multiple spares
        spares = [disk["name"] for disk in call("disk.get_unused")[:2]]
        assert len(spares) == 2

        result = call("pool.update", pool["id"], {"topology": {"spares": spares}}, job=True)
        assert {disk["disk"] for disk in result["topology"]["spare"]} == set(spares)
