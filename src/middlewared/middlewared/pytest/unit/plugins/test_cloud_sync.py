from unittest.mock import Mock

import pytest

from middlewared.plugins.cloud_sync import get_dataset_recursive, FsLockManager, lsjson_error_excerpt


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


@pytest.mark.parametrize("error,excerpt", [
    (
        "2019/09/18 12:26:40 ERROR : : error listing: InvalidAccessKeyId: The AWS Access Key Id you provided does not "
        "exist in our records.\n\tstatus code: 403, request id: 26089FA2BCBF0B60, host id: A6E42cyE7S+KyVKBJh5DRDu/Jv+F"
        "rd6LvXL5A0fLQyMhCvidM7JHA2FY2mLkn4h1IkepFU7G/BE=\n2019/09/18 12:26:40 Failed to lsjson: error in ListJSON: "
        "InvalidAccessKeyId: The AWS Access Key Id you provided does not exist in our records.\n\tstatus code: 403, "
        "request id: 26089FA2BCBF0B60, host id: A6E42cyE7S+KyVKBJh5DRDu/Jv+Frd6LvXL5A0fLQyMhCvidM7JHA2FY2mLkn4h1IkepFU7"
        "G/BE=\n",

        "InvalidAccessKeyId: The AWS Access Key Id you provided does not exist in our records."
    ),
    (
        "2019/09/18 12:29:42 Failed to create file system for \"remote:\": Failed to parse credentials: illegal base64 "
        "data at input byte 0\n",

        "Failed to parse credentials: illegal base64 data at input byte 0"
    )
])
def test__lsjson_error_excerpt(error, excerpt):
    assert lsjson_error_excerpt(error) == excerpt
