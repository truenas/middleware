from unittest.mock import Mock

from middlewared.plugins.cloud_sync import get_dataset_recursive, FsLockManager


def test__get_dataset_recursive_1():
    dataset, recursive = get_dataset_recursive(
        [
            {
                "mountpoint": "/mnt/data",
                "children": [
                    {
                        "mountpoint": "/mnt/data/test",
                        "children": []
                    }
                ]
            },
            {
                "mountpoint": "/mnt/data/test",
                "children": []
            }
        ],
        "/mnt/data",
    )

    assert dataset["mountpoint"] == "/mnt/data"
    assert recursive is True


def test__get_dataset_recursive_2():
    dataset, recursive = get_dataset_recursive(
        [
            {
                "mountpoint": "/mnt/data",
                "children": [
                    {
                        "mountpoint": "/mnt/data/test",
                        "children": []
                    }
                ]
            },
            {
                "mountpoint": "/mnt/data/test",
                "children": []
            }
        ],
        "/mnt/data/test",
    )

    assert dataset["mountpoint"] == "/mnt/data/test"
    assert recursive is False


def test__get_dataset_recursive_3():
    dataset, recursive = get_dataset_recursive(
        [
            {
                "mountpoint": "/mnt/data",
                "children": [
                    {
                        "mountpoint": "/mnt/data/test",
                        "children": []
                    }
                ]
            },
            {
                "mountpoint": "/mnt/data/test",
                "children": []
            }
        ],
        "/mnt/data/test2",
    )

    assert dataset["mountpoint"] == "/mnt/data"
    assert recursive is False


def test__get_dataset_recursive_4():
    dataset, recursive = get_dataset_recursive(
        [
            {
                "mountpoint": "/mnt/data",
                "children": [
                    {
                        "mountpoint": "/mnt/data/backup",
                        "children": [
                            {
                                "mountpoint": "/mnt/data/backup/test0/test1/test2",
                                "children": [],
                            }
                        ]
                    }
                ]
            },
            {
                "mountpoint": "/mnt/data/backup",
                "children": [
                    {
                        "mountpoint": "/mnt/data/backup/test0/test1/test2",
                        "children": [],
                    }
                ]
            },
            {
                "mountpoint": "/mnt/data/backup/test0/test1/test2",
                "children": [],
            }
        ],
        "/mnt/data/backup/test0",
    )

    assert dataset["mountpoint"] == "/mnt/data/backup"
    assert recursive is True


def test__get_dataset_recursive_5():
    dataset, recursive = get_dataset_recursive(
        [
            {
                "mountpoint": "/mnt/data",
                "children": [
                    {
                        "mountpoint": "/mnt/data/backup",
                        "children": [
                            {
                                "mountpoint": "/mnt/data/backup/test0/test1/test2",
                                "children": [],
                            }
                        ]
                    }
                ]
            },
            {
                "mountpoint": "/mnt/data/backup",
                "children": [
                    {
                        "mountpoint": "/mnt/data/backup/test0/test1/test2",
                        "children": [],
                    }
                ]
            },
            {
                "mountpoint": "/mnt/data/backup/test0/test1/test2",
                "children": [],
            }
        ],
        "/mnt/data/backup/test0/test3",
    )

    assert dataset["mountpoint"] == "/mnt/data/backup"
    assert recursive is False


def test__fs_lock_manager_1():
    flm = FsLockManager()
    flm._lock = Mock
    flm._choose_lock = lambda lock, direction: lock

    lock = flm.lock("/mnt/tank/work", Mock())

    assert flm.lock("/mnt/tank", Mock()) == lock


def test__fs_lock_manager_2():
    flm = FsLockManager()
    flm._lock = Mock
    flm._choose_lock = lambda lock, direction: lock

    lock = flm.lock("/mnt/tank/work", Mock())

    assert flm.lock("/mnt/tank/work/temp", Mock()) == lock


def test__fs_lock_manager_3():
    flm = FsLockManager()
    flm._lock = Mock
    flm._choose_lock = lambda lock, direction: lock

    lock = flm.lock("/mnt/tank/work", Mock())

    assert flm.lock("/mnt/tank/temp", Mock()) != lock
