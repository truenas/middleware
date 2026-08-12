import pytest

from middlewared.plugins.container.migrate import usb_id


@pytest.mark.parametrize('value,expected', [
    # How incus writes them.
    ('046d', '0x046d'),
    ('C52B', '0xc52b'),
    # Already prefixed: prefixing again produced `0x0x046d`, which named no device and was
    # accepted by a pattern that only asks for a `0x` prefix.
    ('0x046d', '0x046d'),
    ('0X046D', '0x046d'),
])
def test_usb_id_is_prefixed_exactly_once(value, expected):
    assert usb_id(value) == expected
