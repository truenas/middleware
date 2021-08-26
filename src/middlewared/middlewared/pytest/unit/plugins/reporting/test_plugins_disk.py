from unittest.mock import patch

import pytest

from middlewared.plugins.reporting.plugins import DiskPlugin


@pytest.mark.parametrize("identifier,existing_files,result", [
    ("sda", [], "sda"),
    ("nvme0n1", ["/dev/nvme0c0n1"], "nvme0n1"),
    ("nvme0n1", ["/var/db/collectd/rrd/localhost/disk-nvme0c0n1/disk_octets.rrd"], "nvme0n1"),
    ("nvme0n1", ["/dev/nvme0c0n1", "/var/db/collectd/rrd/localhost/disk-nvme0c0n1/disk_octets.rrd"], "nvme0c0n1"),
])
def test__disk_plugin__encode(identifier, existing_files, result):
    with patch("middlewared.plugins.reporting.plugins.os.path.exists") as exists:
        exists.side_effect = lambda path: path in existing_files

        assert DiskPlugin(None).encode(identifier) == result
