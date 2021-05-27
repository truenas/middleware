# flake8: noqa
import io
import textwrap
from unittest.mock import Mock

import pytest

from middlewared.plugins.cloud_sync import (
    get_dataset_recursive, FsLockManager, lsjson_error_excerpt, RcloneVerboseLogCutter
)


def test__get_dataset_recursive_1():
    dataset, recursive = get_dataset_recursive(
        [
            {
                "children": [
                    {
                        "children": [],
                        "properties": {
                            "mountpoint": {
                                "value": "/mnt/data/test",
                            }
                        }
                    }
                ],
                "properties": {
                    "mountpoint": {
                        "value": "/mnt/data",
                    }
                }
            },
            {
                "children": [],
                "properties": {
                    "mountpoint": {
                        "value": "/mnt/data/test",
                    }
                }
            }
        ],
        "/mnt/data",
    )

    assert dataset["properties"]["mountpoint"]["value"] == "/mnt/data"
    assert recursive is True


def test__get_dataset_recursive_2():
    dataset, recursive = get_dataset_recursive(
        [
            {
                "children": [
                    {
                        "children": [],
                        "properties": {
                            "mountpoint": {
                                "value": "/mnt/data/test",
                            }
                        }
                    }
                ],
                "properties": {
                    "mountpoint": {
                        "value": "/mnt/data",
                    }
                }
            },
            {
                "children": [],
                "properties": {
                    "mountpoint": {
                        "value": "/mnt/data/test",
                    }
                }
            }
        ],
        "/mnt/data/test",
    )

    assert dataset["properties"]["mountpoint"]["value"] == "/mnt/data/test"
    assert recursive is False


def test__get_dataset_recursive_3():
    dataset, recursive = get_dataset_recursive(
        [
            {
                "children": [
                    {
                        "children": [],
                        "properties": {
                            "mountpoint": {
                                "value": "/mnt/data/test",
                            }
                        }
                    }
                ],
                "properties": {
                    "mountpoint": {
                        "value": "/mnt/data",
                    }
                }
            },
            {
                "children": [],
                "properties": {
                    "mountpoint": {
                        "value": "/mnt/data/test",
                    }
                }
            }
        ],
        "/mnt/data/test2",
    )

    assert dataset["properties"]["mountpoint"]["value"] == "/mnt/data"
    assert recursive is False


def test__get_dataset_recursive_4():
    dataset, recursive = get_dataset_recursive(
        [
            {
                "children": [
                    {
                        "children": [
                            {
                                "children": [],
                                "properties": {
                                    "mountpoint": {
                                        "value": "/mnt/data/backup/test0/test1/test2",
                                    }
                                }
                            }
                        ],
                        "properties": {
                            "mountpoint": {
                                "value": "/mnt/data/backup",
                            }
                        }
                    }
                ],
                "properties": {
                    "mountpoint": {
                        "value": "/mnt/data",
                    }
                }
            },
            {
                "children": [
                    {
                        "children": [],
                        "properties": {
                            "mountpoint": {
                                "value": "/mnt/data/backup/test0/test1/test2",
                            }
                        }
                    }
                ],
                "properties": {
                    "mountpoint": {
                        "value": "/mnt/data/backup",
                    }
                }
            },
            {
                "children": [],
                "properties": {
                    "mountpoint": {
                        "value": "/mnt/data/backup/test0/test1/test2",
                    }
                }
            }
        ],
        "/mnt/data/backup/test0",
    )

    assert dataset["properties"]["mountpoint"]["value"] == "/mnt/data/backup"
    assert recursive is True


def test__get_dataset_recursive_5():
    dataset, recursive = get_dataset_recursive(
        [
            {
                "children": [
                    {
                        "children": [
                            {
                                "children": [],
                                "properties": {
                                    "mountpoint": {
                                        "value": "/mnt/data/backup/test0/test1/test2",
                                    }
                                }
                            }
                        ],
                        "properties": {
                            "mountpoint": {
                                "value": "/mnt/data/backup",
                            }
                        }
                    }
                ],
                "properties": {
                    "mountpoint": {
                        "value": "/mnt/data",
                    }
                }
            },
            {
                "children": [
                    {
                        "children": [],
                        "properties": {
                            "mountpoint": {
                                "value": "/mnt/data/backup/test0/test1/test2",
                            }
                        }
                    }
                ],
                "properties": {
                    "mountpoint": {
                        "value": "/mnt/data/backup",
                    }
                }
            },
            {
                "children": [],
                "properties": {
                    "mountpoint": {
                        "value": "/mnt/data/backup/test0/test1/test2",
                    }
                }
            }
        ],
        "/mnt/data/backup/test0/test3",
    )

    assert dataset["properties"]["mountpoint"]["value"] == "/mnt/data/backup"
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


def INFO(v):
    return textwrap.dedent(f"""\
        2020/01/22 22:32:{v:02d} INFO  : 
        Transferred:   	  752.465G / 27.610 TBytes, 3%, 7.945 MBytes/s, ETA 5w6d1h16m55s
        Errors:               478 (retrying may help)
        Checks:                89 / 89, 100%
        Transferred:           75 / 3546, 2%
        Elapsed time:  26h56m23.1s
        Transferring:
         *         Cam (2018)/Cam (2018) WEBDL-1080p.mkv:  0% /3.470G, 0/s, -
         * Call Me by Your Name (…2017) Bluray-1080p.mkv:  0% /9.839G, 0/s, -
         * Can't Take It Back (20…(2017) WEBDL-1080p.mkv:  0% /3.035G, 0/s, -
         * Candleshoe (1977)/Cand… (1977) WEBDL-720p.mkv:  0% /2.865G, 0/s, -
    
    """)


@pytest.mark.parametrize("input,output", [
    (f"WELCOME TO RCLONE\n{INFO(1)}{INFO(2)}BYE!\n", f"WELCOME TO RCLONE\n{INFO(1)}BYE!\n"),
    (f"WELCOME TO RCLONE\n{INFO(1)}{INFO(2)}{INFO(3)}{INFO(4)}{INFO(5)}{INFO(6)}BYE!\n",
     f"WELCOME TO RCLONE\n{INFO(1)}{INFO(6)}BYE!\n"),
    (f"WELCOME TO RCLONE\n{INFO(1)}{INFO(2)[:300]}\nKilled (9)",
     f"WELCOME TO RCLONE\n{INFO(1)}{INFO(2)[:300]}\nKilled (9)"),
    (f"2020/01/27 13:16:15 INFO  : S3 bucket ixsystems: Waiting for transfers to finish\n"
     f"{INFO(1)}{INFO(2)}{INFO(3)}{INFO(4)}{INFO(5)}{INFO(6)}BYE!\n",
     f"2020/01/27 13:16:15 INFO  : S3 bucket ixsystems: Waiting for transfers to finish\n{INFO(1)}{INFO(6)}BYE!\n")
])
def test__RcloneVerboseLogCutter(input, output):
    cutter = RcloneVerboseLogCutter(5)
    f = io.StringIO(input)
    out = ""
    while True:
        line = f.readline()
        if not line:
            break

        result = cutter.notify(line)
        if result:
             out += result

    result = cutter.flush()
    if result:
        out += result

    assert out == output
