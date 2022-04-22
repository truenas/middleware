import pytest

from middlewared.plugins.reporting.iostat import DiskStats


@pytest.mark.parametrize("device,disk", [
    ("sda", "sda"),
    ("sdab", "sdab"),
    ("sda1", "sda"),
    ("sda11", "sda"),
    ("sdab1", "sdab"),
    ("sdab11", "sdab"),
    ("nvme0c0n1", None),
    ("nvme0c11n1", None),
    ("nvme0n1p1", None),
    ("nvme0n1p11", None),
    ("nvme0n1", "nvme0n1"),
    ("nvme0n11", "nvme0n11"),
])
def test__get_disk(device, disk):
    assert DiskStats(None, None).get_disk(device) == disk
