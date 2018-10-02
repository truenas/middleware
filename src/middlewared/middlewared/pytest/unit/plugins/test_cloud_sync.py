from middlewared.plugins.cloud_sync import get_dataset_recursive


def test__1():
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
            }
        ],
        "/mnt/data",
    )

    assert dataset["mountpoint"] == "/mnt/data"
    assert recursive is True


def test__2():
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
            }
        ],
        "/mnt/data/test",
    )

    assert dataset["mountpoint"] == "/mnt/data/test"
    assert recursive is False


def test__3():
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
            }
        ],
        "/mnt/data/test2",
    )

    assert dataset["mountpoint"] == "/mnt/data"
    assert recursive is False


def test__4():
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
            }
        ],
        "/mnt/data/backup/test0",
    )

    assert dataset["mountpoint"] == "/mnt/data/backup"
    assert recursive is True


def test__5():
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
            }
        ],
        "/mnt/data/backup/test0/test3",
    )

    assert dataset["mountpoint"] == "/mnt/data/backup"
    assert recursive is False
