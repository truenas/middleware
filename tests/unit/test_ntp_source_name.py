import pytest

from middlewared.plugins.ntp.peers import SOURCE_NAME, parse_source_name


@pytest.mark.parametrize(
    "name,expected",
    [
        (b"time.cloudflare.com", "time.cloudflare.com"),
        (b"192.0.2.1", "192.0.2.1"),
        # chronyc prints these as ?
        (b"", "?"),
        (b"x" * 256, "?"),
        (b"bad name", "?"),
        (b"bad\nname", "?"),
    ],
)
def test_parse_source_name(name, expected):
    assert parse_source_name(SOURCE_NAME.pack(name)) == expected
