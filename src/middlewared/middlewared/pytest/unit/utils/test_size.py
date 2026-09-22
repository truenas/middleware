import pytest

from middlewared.utils.size import zfs_size_bytes


@pytest.mark.parametrize(
    "value, expected",
    [
        ("128K", 131072),
        ("128k", 131072),
        ("128KB", 131072),
        ("128KiB", 131072),
        ("128kib", 131072),
        ("3M", 3145728),
        ("2G", 2147483648),
        ("1T", 1099511627776),
        ("1P", 1125899906842624),
        ("1E", 1152921504606846976),
        ("512", 512),
        ("512B", 512),
        (" 16K ", 16384),
        ("1.5K", 1536),
        ("0.5M", 524288),
        ("0", 0),
        (0, 0),
        (4096, 4096),
    ],
)
def test_zfs_size_bytes_parses(value, expected):
    assert zfs_size_bytes(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", "1.3K", "0.1", "-1", "-1K", "1X", "1KX", "512iB", "K", "none", "auto", -1, True, None, 1.0, [1]],
)
def test_zfs_size_bytes_rejects_with_value_error(value):
    with pytest.raises(ValueError):
        zfs_size_bytes(value)
