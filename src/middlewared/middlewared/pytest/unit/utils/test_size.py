import pytest

from middlewared.utils.size import zfs_size_bytes


@pytest.mark.parametrize(
    "value, expected",
    [
        ("128K", 131072),
        ("128kib", 131072),
        ("128KB", 131072),
        ("2G", 2147483648),
        ("512", 512),
        ("512B", 512),
        (" 16K ", 16384),
        ("1.5K", 1536),
        (0, 0),
    ],
)
def test_zfs_size_bytes_parses(value, expected):
    assert zfs_size_bytes(value) == expected


@pytest.mark.parametrize(
    "value",
    ["1.3K", "-1K", "1X", "512iB", "none", -1, True, None],
)
def test_zfs_size_bytes_rejects_with_value_error(value):
    with pytest.raises(ValueError):
        zfs_size_bytes(value)
