import pytest
import yaml

from middlewared.utils.libvirt.nic import normalize_mac, random_mac


@pytest.mark.parametrize(
    "value,expected",
    [
        # How incus writes them.
        ("00:16:3e:aa:bb:cc", "00:16:3e:aa:bb:cc"),
        # The same address in a spelling libvirt's `defineXML` cannot parse.
        ("00:16:3E:AA:BB:CC", "00:16:3e:aa:bb:cc"),
        ("00-16-3e-aa-bb-cc", "00:16:3e:aa:bb:cc"),
        ("00163eaabbcc", "00:16:3e:aa:bb:cc"),
        ("00:16-3e:AAbbCC", "00:16:3e:aa:bb:cc"),
    ],
)
def test_normalize_mac_collapses_to_libvirt_form(value, expected):
    assert normalize_mac(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        # PyYAML resolves an unquoted `52:54:00:12:34:56` as a YAML 1.1 base-60 integer.
        41135085296,
        "",
        "not-a-mac",
        # Too short, too long, and not hex.
        "00:16:3e:aa:bb",
        "00:16:3e:aa:bb:cc:dd",
        "00:16:3e:aa:bb:gg",
        # `$` also matches before a trailing newline, which libvirt still cannot parse.
        "00:16:3e:aa:bb:cc\n",
    ],
)
def test_normalize_mac_rejects_what_is_not_an_address(value):
    assert normalize_mac(value) is None


def test_yaml_resolves_a_numeric_mac_as_an_integer():
    """The manifest value the migration reads is not always a string.

    Every octet of qemu's own `52:54:00:` range can be numeric and below 60, which is the YAML 1.1
    sexagesimal form, so an unquoted address of that shape arrives as an `int`.
    """
    assert yaml.safe_load("hwaddr: 52:54:00:12:34:56") == {"hwaddr": 41135085296}
    assert yaml.safe_load("hwaddr: 00:16:3e:aa:bb:cc") == {"hwaddr": "00:16:3e:aa:bb:cc"}


def test_random_mac_is_already_in_libvirt_form():
    mac = random_mac()
    assert normalize_mac(mac) == mac
