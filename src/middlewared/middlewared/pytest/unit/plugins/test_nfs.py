from mock import ANY, Mock, patch

from middlewared.plugins.nfs import SharingNFSService


def test__sharing_nfs_service__validate_paths__same_filesystem():
    with patch("middlewared.plugins.nfs.os.stat", lambda dev: {
        "/mnt/data-1": Mock(st_dev=1),
        "/mnt/data-1/a": Mock(st_dev=1),
        "/mnt/data-1/b": Mock(st_dev=1),
    }[dev]):
        middleware = Mock()

        verrors = Mock()

        SharingNFSService(middleware).validate_paths(
            {
                "paths": ["/mnt/data-1/a", "/mnt/data-1/b"],
            },
            "sharingnfs_update",
            verrors,
        )

        assert not verrors.add.called


def test__sharing_nfs_service__validate_paths__not_same_filesystem():
    with patch("middlewared.plugins.nfs.os.stat", lambda dev: {
        "/mnt/data-1": Mock(st_dev=1),
        "/mnt/data-2": Mock(st_dev=2),
        "/mnt/data-1/d": Mock(st_dev=1),
        "/mnt/data-2/d": Mock(st_dev=2),
    }[dev]):
        middleware = Mock()

        verrors = Mock()

        SharingNFSService(middleware).validate_paths(
            {
                "paths": ["/mnt/data-1/d", "/mnt/data-2/d"],
            },
            "sharingnfs_update",
            verrors,
        )

        verrors.add.assert_called_once_with("sharingnfs_update.paths.1",
                                            "Paths for a NFS share must reside within the same filesystem")


def test__sharing_nfs_service__validate_hosts_and_networks__host_is_32_network():
    with patch("middlewared.plugins.nfs.os.stat", lambda dev: {
        "/mnt/data/a": Mock(st_dev=1),
        "/mnt/data/b": Mock(st_dev=1),
    }[dev]):
        middleware = Mock()

        verrors = Mock()

        SharingNFSService(middleware).validate_hosts_and_networks(
            [
                {
                    "paths": ["/mnt/data/a"],
                    "hosts": ["192.168.0.1"],
                    "networks": [],
                    "alldirs": False,
                },
            ],
            {
                "paths": ["/mnt/data/b"],
                "hosts": ["192.168.0.1"],
                "networks": [],
                "alldirs": False,
            },
            "sharingnfs_update",
            verrors,
            {
                "192.168.0.1": "192.168.0.1",
            },
        )

        verrors.add.assert_called_once_with("sharingnfs_update.hosts.0", ANY)


def test__sharing_nfs_service__validate_hosts_and_networks__dataset_is_already_exported():
    with patch("middlewared.plugins.nfs.os.stat", lambda dev: {
        "/mnt/data/a": Mock(st_dev=1),
        "/mnt/data/b": Mock(st_dev=1),
    }[dev]):
        middleware = Mock()

        verrors = Mock()

        SharingNFSService(middleware).validate_hosts_and_networks(
            [
                {
                    "paths": ["/mnt/data/a"],
                    "hosts": [],
                    "networks": ["192.168.0.0/24"],
                    "alldirs": False,
                },
            ],
            {
                "paths": ["/mnt/data/b"],
                "hosts": [],
                "networks": ["192.168.0.0/24"],
                "alldirs": False,
            },
            "sharingnfs_update",
            verrors,
            {
                "192.168.0.1": "192.168.0.1",
            },
        )

        verrors.add.assert_called_once_with("sharingnfs_update.networks.0", ANY)


def test__sharing_nfs_service__validate_hosts_and_networks__fs_is_already_exported_for_world():
    with patch("middlewared.plugins.nfs.os.stat", lambda dev: {
        "/mnt/data/a": Mock(st_dev=1),
        "/mnt/data/b": Mock(st_dev=1),
    }[dev]):
        middleware = Mock()

        verrors = Mock()

        SharingNFSService(middleware).validate_hosts_and_networks(
            [
                {
                    "paths": ["/mnt/data/a"],
                    "hosts": ["192.168.0.1"],
                    "networks": [],
                    "alldirs": False,
                },
            ],
            {
                "paths": ["/mnt/data/b"],
                "hosts": [],
                "networks": [],
                "alldirs": False,
            },
            "sharingnfs_update",
            verrors,
            {
                "192.168.0.1": "192.168.0.1",
            },
        )

        verrors.add.assert_called_once_with("sharingnfs_update.networks", ANY)
