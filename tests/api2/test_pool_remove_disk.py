import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh

from auto_config import ha
pytestmark = [
    pytest.mark.skipif(ha, reason='Skipping for HA testing'),
    pytest.mark.disk,
    pytest.mark.zfs,
]


def test_waits_for_device_removal():
    with another_pool(topology=(4, lambda disks: {
        "data": [
            {"type": "MIRROR", "disks": disks[0:2]},
            {"type": "MIRROR", "disks": disks[2:4]}
        ],
    })) as pool:
        ssh(f"dd if=/dev/urandom of=/mnt/{pool['name']}/blob bs=1M count=1000")
        call("pool.remove", pool["id"], {"label": pool["topology"]["data"][0]["guid"]}, job=True)
