import pytest

from middlewared.utils.size import format_size


@pytest.mark.parametrize(
    "size, expected",
    [
        (0, "0 bytes"),
        (1, "1 byte"),
        (-1, "-1 bytes"),
        (100, "100 bytes"),
        (999, "999 bytes"),
        (1023, "1023 bytes"),
        (-1024, "-1024 bytes"),
        (1024, "1 KiB"),
        (2 * 1024, "2 KiB"),
        (1500, "1.46 KiB"),
        (1535, "1.5 KiB"),
        (1536, "1.5 KiB"),
        (1048576, "1 MiB"),
        (1500000, "1.43 MiB"),
        (1073741824, "1 GiB"),
        (1234567890, "1.15 GiB"),
        (1099511627776, "1 TiB"),
        (5 * 1024**4, "5 TiB"),
        (1024**5, "1 PiB"),
        (1024**6, "1 EiB"),
        (1024**7, "1 ZiB"),
        (1024**8, "1 YiB"),
        (1024**9, "1024 YiB"),
    ],
)
def test_format_size(size, expected):
    assert format_size(size) == expected
