import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from middlewared.api.current import SharingNFSEntry
from middlewared.plugins.nfs_.share_hosts import validate_hosts_and_networks


def share(path, hosts, networks):
    return SharingNFSEntry(
        id=1,
        path=path,
        dataset=None,
        relative_path=None,
        locked=False,
        hosts=hosts,
        networks=networks,
    )


def context():
    ctx = Mock()
    ctx.middleware.call = AsyncMock(side_effect=lambda method, path: SimpleNamespace(realpath=path))
    return ctx


def validate(other_shares, data, dns_cache, verrors):
    asyncio.run(
        validate_hosts_and_networks(context(), other_shares, data, "sharingnfs_update", verrors, dns_cache)
    )


def test__validate_hosts_and_networks__host_is_32_network():
    verrors = Mock()

    validate(
        [share("/mnt/data/a", ["192.168.0.1"], [])],
        share("/mnt/data/b", ["192.168.0.1"], []),
        {"192.168.0.1": "192.168.0.1"},
        verrors,
    )

    # NAS-123042: A passing condition
    verrors.add.assert_not_called()


def test__validate_hosts_and_networks__dataset_is_already_exported():
    verrors = Mock()

    validate(
        [share("/mnt/data/a", [], ["192.168.0.0/24"])],
        share("/mnt/data/b", [], ["192.168.0.0/24"]),
        {"192.168.0.1": "192.168.0.1"},
        verrors,
    )

    # NAS-123042: A passing condition
    verrors.add.assert_not_called()


def test__validate_hosts_and_networks__fs_is_already_exported_for_world():
    verrors = Mock()

    validate(
        [share("/mnt/data/a", ["192.168.0.1"], [])],
        share("/mnt/data/b", [], []),
        {"192.168.0.1": "192.168.0.1"},
        verrors,
    )

    # This is now a passing condition: NAS-120957
    verrors.add.assert_not_called()
