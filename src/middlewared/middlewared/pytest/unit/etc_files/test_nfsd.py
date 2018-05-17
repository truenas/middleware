from collections import defaultdict
import ipaddress

from mock import Mock, patch

from middlewared.etc_files.nfsd import build_share_targets


def test__build_share_targets__increment_works():
    with patch("middlewared.etc_files.nfsd.os.stat") as stat:
        stat.return_value = Mock(st_dev=1234)

        networks_pool = defaultdict(lambda: defaultdict(lambda: 0))
        networks_pool[1234][ipaddress.ip_network("192.168.0.0/24")] = 7

        assert build_share_targets({
            "paths": ["/mnt/vol"],
            "hosts": [],
            "networks": ["192.168.0.0/24"],
        }, networks_pool) == ["-network 192.168.0.7/24"]


def test__build_share_targets__skips_on_overflow():
    with patch("middlewared.etc_files.nfsd.os.stat") as stat:
        stat.return_value = Mock(st_dev=1234)

        networks_pool = defaultdict(lambda: defaultdict(lambda: 0))
        networks_pool[1234][ipaddress.ip_network("192.168.0.0/24")] = 256

        assert build_share_targets({
            "paths": ["/mnt/vol"],
            "hosts": [],
            "networks": ["192.168.0.0/24", "192.168.1.0/24"],
        }, networks_pool) == ["-network 192.168.1.0/24"]


def test__build_share_targets__skips_repeated_host():
    with patch("middlewared.etc_files.nfsd.os.stat") as stat:
        stat.return_value = Mock(st_dev=1234)

        networks_pool = defaultdict(lambda: defaultdict(lambda: 0))
        networks_pool[1234][ipaddress.ip_network("192.168.0.4/32")] = 1

        assert build_share_targets({
            "paths": ["/mnt/vol"],
            "hosts": ["192.168.0.4"],
            "networks": [],
        }, networks_pool) == []
