import pytest

from middlewared.plugins.fc.utils import (colon_hex_as_naa, filter_by_wwpns_hex_string, is_fc_addr, naa_to_int,
                                          str_to_naa, wwn_as_colon_hex, wwpn_to_vport_naa)


@pytest.mark.parametrize(
    "param,expected",
    [
        (None, None),
        (1234, None),
        ("aa:bb:cc:dd", None),
        ("12:34:56:78:aa:bb:cc:dd", "naa.12345678aabbccdd"),
    ],
)
def test__colon_hex_as_naa(param, expected):
    assert colon_hex_as_naa(param) == expected


@pytest.mark.parametrize(
    "params,expected",
    [
        (("naa.12345678aabbccdd", None), [['port_name', '=', '0x12345678aabbccdd']]),
        ((None, "naa.12345678aabbccdd"), [['port_name', '=', '0x12345678aabbccdd']]),
        (("naa.0123456789abcdef", "naa.12345678aabbccdd"), [['OR',
                                                            [
                                                                ['port_name', '=', '0x0123456789abcdef'],
                                                                ['port_name', '=', '0x12345678aabbccdd'],
                                                            ]]]),
    ],
)
def test__filter_by_wwpns_hex_string(params, expected):
    assert filter_by_wwpns_hex_string(*params) == expected


@pytest.mark.parametrize(
    "param,expected",
    [
        ("12:34:56:78:aa:bb:cc:dd", True),
        ("12:34:56:78:aa:bb:cc", False),
        ("12:34:56:78:aa:bb:cc:dd:ee", False),
        ("naa.12345678aabbccdd", True),
        ("naa.12345678aabbcc", False),
        ("naa.12345678aabbccddee", False),
        ("", False),
        (None, False),
        ("aa:bb:cc:dd", False),
        ("naa.aabbccdd", False)
    ],
)
def test__is_fc_addr(param, expected):
    assert is_fc_addr(param) == expected


@pytest.mark.parametrize(
    "param,expected",
    [
        ("naa.12345678aabbccdd", 0x12345678aabbccdd),
        ("naa.12345678aabbccddee", None),
        ("naa.12345678aabbcc", None),
        ("12:34:56:78:aa:bb:cc:dd", None),
        ("0x12345678aabbccdd", None),
        ("12:34:56:78:aa:bb:cc", None),
        ("junk", None),
        ("", None),
        (None, None),
    ],
)
def test__naa_to_int(param, expected):
    assert naa_to_int(param) == expected


@pytest.mark.parametrize(
    "param,expected",
    [
        ("naa.12345678aabbccdd", "naa.12345678aabbccdd"),
        ("naa.12345678aabbccddee", None),
        ("naa.12345678aabbcc", None),
        ("12:34:56:78:aa:bb:cc:dd", "naa.12345678aabbccdd"),
        ("0x12345678aabbccdd", "naa.12345678aabbccdd"),
        ("12:34:56:78:aa:bb:cc", None),
        ("junk", None),
        ("", None),
        (None, None),
    ],
)
def test__str_to_naa(param, expected):
    assert str_to_naa(param) == expected


@pytest.mark.parametrize(
    "param,expected",
    [
        ("naa.12345678aabbccdd", "12:34:56:78:aa:bb:cc:dd"),
        ("12:34:56:78:aa:bb:cc:dd", "12:34:56:78:aa:bb:cc:dd"),
        ("0x12345678aabbccdd", "12:34:56:78:aa:bb:cc:dd"),
        ("12:34:56:78:aa:bb:cc", None),
        ("junk", None),
        ("", None),
        (None, None),
    ],
)
def test__wwn_as_colon_hex(param, expected):
    assert wwn_as_colon_hex(param) == expected


@pytest.mark.parametrize(
    "params,expected",
    [
        (("naa.2100001234567890", 0), "naa.2100001234567890"),
        (("naa.2100001234567890", 1), "naa.2200001234567890"),
        (("naa.2100001234567890", 2), "naa.2300001234567890"),
        (("21:00:00:12:34:56:78:90", 0), "naa.2100001234567890"),
        (("21:00:00:12:34:56:78:90", 1), "naa.2200001234567890"),
        (("21:00:00:12:34:56:78:90", 2), "naa.2300001234567890"),
        (("0x2100001234567890", 0), "naa.2100001234567890"),
        (("0x2100001234567890", 1), "naa.2200001234567890"),
        (("0x2100001234567890", 2), "naa.2300001234567890"),
        ((0x2100001234567890, 0), "naa.2100001234567890"),
        ((0x2100001234567890, 1), "naa.2200001234567890"),
        ((0x2100001234567890, 2), "naa.2300001234567890"),
        (("", 0), None),
        ((None, 0), None),
    ],
)
def test__wwpn_to_vport_naa(params, expected):
    assert wwpn_to_vport_naa(*params) == expected
