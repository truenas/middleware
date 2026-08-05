from copy import deepcopy

import pytest

from middlewared.utils.usb import (
    DROP_BAD_PORT, DROP_BAD_USB_ID, DROP_DEVICE_NUMBER, DROP_NO_IDENTITY, DROP_ROOT_HUB,
    libvirt_usb_name_to_port, migrate_usb_device_attributes, normalize_usb_id,
)


@pytest.mark.parametrize('value,expected', [
    # libvirt nodedev names
    ('usb_1_4', '1-4'),
    ('usb_5_1_1', '5-1.1'),
    ('usb_1_4_2_3', '1-4.2.3'),
    ('usb_001_004', '1-4'),
    ('usb_0_000', '0-0'),
    ('usb_1_1.2', '1-1.2'),
    ('usb_usb1', 'usb1'),
    ('usb_3', '3'),
    ('  usb_1_4  ', '1-4'),
    # already a port path, left alone
    ('1-4', '1-4'),
    ('1-4.2', '1-4.2'),
    ('5-1.1.3', '5-1.1.3'),
    ('  1-4  ', '1-4'),
    # not a libvirt USB nodedev name, left alone
    ('pci_0000_00_02_0', 'pci_0000_00_02_0'),
    ('usb1', 'usb1'),
    ('', ''),
])
def test_libvirt_usb_name_to_port(value, expected):
    assert libvirt_usb_name_to_port(value) == expected


@pytest.mark.parametrize('value', [
    'usb_1_4',
    'usb_5_1_1',
    'usb_001_004',
    'usb_1_1.2',
    'usb_usb1',
    '1-4.2',
    'pci_0000_00_02_0',
])
def test_libvirt_usb_name_to_port_is_idempotent(value):
    once = libvirt_usb_name_to_port(value)
    assert libvirt_usb_name_to_port(once) == once


@pytest.mark.parametrize('value,expected', [
    ('abcd', '0xabcd'),
    ('0xabcd', '0xabcd'),
    ('0x0xabcd', '0xabcd'),
    ('0XABCD', '0xabcd'),
    ('0x0X0xABcd', '0xabcd'),
    ('  0xABCD  ', '0xabcd'),
    ('1d6b', '0x1d6b'),
    # short ids are padded out to the four hex digits an id is wide
    ('1', '0x0001'),
    ('0x1', '0x0001'),
    ('0xB', '0x000b'),
    ('2b', '0x002b'),
    ('0x2B', '0x002b'),
    ('abc', '0x0abc'),
    ('0xabc', '0x0abc'),
    ('0x0xABC', '0x0abc'),
    ('  0XaBc  ', '0x0abc'),
    ('0002', '0x0002'),
    # too wide to be an id, but truncating would invent a different one
    ('0x12345', '0x12345'),
    # junk passes through untouched rather than raising
    ('not-hex', 'not-hex'),
    ('0x', '0x'),
    ('', ''),
])
def test_normalize_usb_id(value, expected):
    assert normalize_usb_id(value) == expected


@pytest.mark.parametrize('value', ['abcd', '0x0xabcd', '0XABCD', '0x1', 'abc', '0x0xABC', '0x12345', 'not-hex', '0x'])
def test_normalize_usb_id_is_idempotent(value):
    once = normalize_usb_id(value)
    assert normalize_usb_id(once) == once


# Each case is (attributes, device_is_port_path, expected attributes, expected drop reason).
MIGRATE_CASES = [
    (
        {'dtype': 'USB', 'device': 'usb_1_4', 'usb': None},
        True,
        {'dtype': 'USB', 'port': '1-4', 'usb': None},
        None,
    ),
    (
        {'dtype': 'USB', 'device': 'usb_5_1_1', 'usb': None},
        True,
        {'dtype': 'USB', 'port': '5-1.1', 'usb': None},
        None,
    ),
    (
        {'dtype': 'USB', 'device': 'usb_001_004', 'usb': None},
        True,
        {'dtype': 'USB', 'port': '1-4', 'usb': None},
        None,
    ),
    (
        {'dtype': 'USB', 'device': 'usb_1_1.2', 'usb': None},
        True,
        {'dtype': 'USB', 'port': '1-1.2', 'usb': None},
        None,
    ),
    (
        {'dtype': 'USB', 'device': '1-4.2', 'usb': None},
        True,
        {'dtype': 'USB', 'port': '1-4.2', 'usb': None},
        None,
    ),
    (
        # identified by ids only, so it does not matter how `device` would be read
        {'dtype': 'USB', 'device': None, 'usb': {'vendor_id': '0x0x1d6b', 'product_id': '0xABCD'}},
        True,
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x1d6b', 'product_id': '0xabcd'}},
        None,
    ),
    (
        {'dtype': 'USB', 'device': None, 'usb': {'vendor_id': '0x0x1d6b', 'product_id': '0xABCD'}},
        False,
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x1d6b', 'product_id': '0xabcd'}},
        None,
    ),
    (
        # ids stored short are padded, otherwise the API cannot read the row back
        {'dtype': 'USB', 'device': None, 'usb': {'vendor_id': '0xabc', 'product_id': '2'}},
        True,
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x0abc', 'product_id': '0x0002'}},
        None,
    ),
    (
        {'dtype': 'USB', 'device': None, 'usb': {'vendor_id': '0xabc', 'product_id': '2'}},
        False,
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x0abc', 'product_id': '0x0002'}},
        None,
    ),
    (
        # the same padding applies to an already migrated row
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '1d6b', 'product_id': '0x2'}},
        True,
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
        None,
    ),
    (
        # both set: the port wins
        {'dtype': 'USB', 'device': 'usb_1_4', 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
        True,
        {'dtype': 'USB', 'port': '1-4', 'usb': None},
        None,
    ),
    (
        # already migrated
        {'dtype': 'USB', 'port': '1-4.2', 'usb': None},
        True,
        {'dtype': 'USB', 'port': '1-4.2', 'usb': None},
        None,
    ),
    (
        {'dtype': 'USB', 'port': '1-4.2', 'usb': None},
        False,
        {'dtype': 'USB', 'port': '1-4.2', 'usb': None},
        None,
    ),
    (
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
        True,
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
        None,
    ),
    (
        # keys we know nothing about are carried over untouched
        {'dtype': 'USB', 'device': 'usb_1_4', 'usb': None, 'controller_type': 'nec-xhci'},
        True,
        {'dtype': 'USB', 'port': '1-4', 'usb': None, 'controller_type': 'nec-xhci'},
        None,
    ),
    (
        # root hub: no port to honour, whichever way the value would be read
        {'dtype': 'USB', 'device': 'usb_usb1', 'usb': None},
        True,
        None,
        DROP_ROOT_HUB,
    ),
    (
        {'dtype': 'USB', 'device': 'usb_usb12', 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
        True,
        None,
        DROP_ROOT_HUB,
    ),
    (
        {'dtype': 'USB', 'device': 'usb_usb1', 'usb': None},
        False,
        None,
        DROP_ROOT_HUB,
    ),
    (
        # a device number names a socket we cannot work out, so nothing is kept
        {'dtype': 'USB', 'device': 'usb_1_4', 'usb': None},
        False,
        None,
        DROP_DEVICE_NUMBER,
    ),
    (
        {'dtype': 'USB', 'device': 'usb_1_4', 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
        False,
        None,
        DROP_DEVICE_NUMBER,
    ),
    (
        # ... even where the digits happen to spell a plausible port path
        {'dtype': 'USB', 'device': '1-4.2', 'usb': None},
        False,
        None,
        DROP_DEVICE_NUMBER,
    ),
    (
        # neither set: there is no device here to describe
        {'dtype': 'USB', 'device': None, 'usb': None},
        True,
        None,
        DROP_NO_IDENTITY,
    ),
    (
        {'dtype': 'USB', 'device': None, 'usb': None},
        False,
        None,
        DROP_NO_IDENTITY,
    ),
    (
        {'dtype': 'USB', 'port': None, 'usb': None},
        True,
        None,
        DROP_NO_IDENTITY,
    ),
    (
        {'dtype': 'USB'},
        True,
        None,
        DROP_NO_IDENTITY,
    ),
    (
        # an id too wide to be one: it cannot be trimmed back into the right device
        {'dtype': 'USB', 'device': None, 'usb': {'vendor_id': '0x12345', 'product_id': '0x0002'}},
        True,
        None,
        DROP_BAD_USB_ID,
    ),
    (
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x1d6b', 'product_id': '0xzz'}},
        True,
        None,
        DROP_BAD_USB_ID,
    ),
    (
        {'dtype': 'USB', 'device': None, 'usb': {'vendor_id': '0x1d6b'}},
        False,
        None,
        DROP_BAD_USB_ID,
    ),
    (
        # a device value that was never a port path in the first place
        {'dtype': 'USB', 'device': 'pci_0000_00_02_0', 'usb': None},
        True,
        None,
        DROP_BAD_PORT,
    ),
    (
        {'dtype': 'USB', 'port': 'not-a-port', 'usb': None},
        True,
        None,
        DROP_BAD_PORT,
    ),
]


@pytest.mark.parametrize('attributes,device_is_port_path,expected,expected_reason', MIGRATE_CASES)
def test_migrate_usb_device_attributes(attributes, device_is_port_path, expected, expected_reason):
    assert migrate_usb_device_attributes(
        attributes, device_is_port_path=device_is_port_path,
    ) == (expected, expected_reason)


@pytest.mark.parametrize('attributes,device_is_port_path', [case[:2] for case in MIGRATE_CASES])
def test_migrate_usb_device_attributes_does_not_mutate_input(attributes, device_is_port_path):
    original = deepcopy(attributes)
    migrate_usb_device_attributes(attributes, device_is_port_path=device_is_port_path)
    assert attributes == original


@pytest.mark.parametrize('attributes,device_is_port_path', [case[:2] for case in MIGRATE_CASES])
def test_migrate_usb_device_attributes_is_idempotent(attributes, device_is_port_path):
    once = migrate_usb_device_attributes(attributes, device_is_port_path=device_is_port_path)
    if once.attributes is None:
        return

    assert migrate_usb_device_attributes(
        once.attributes, device_is_port_path=device_is_port_path,
    ) == once


@pytest.mark.parametrize('device_is_port_path', [True, False])
@pytest.mark.parametrize('attributes', [
    {'dtype': 'USB', 'port': '1-4.2', 'usb': None},
    {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
])
def test_migrate_usb_device_attributes_already_migrated_compares_equal(attributes, device_is_port_path):
    assert migrate_usb_device_attributes(
        attributes, device_is_port_path=device_is_port_path,
    ).attributes == attributes


@pytest.mark.parametrize('attributes,expected', [
    # An identity built from vendor and product ids says nothing about which port the device sits
    # in, so it means the same thing in either table and is kept in both.
    (
        {'dtype': 'USB', 'device': None, 'usb': {'vendor_id': '0xABC', 'product_id': '2'}},
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x0abc', 'product_id': '0x0002'}},
    ),
    (
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
    ),
])
def test_migrate_usb_device_attributes_keeps_ids_in_both_tables(attributes, expected):
    for device_is_port_path in (True, False):
        assert migrate_usb_device_attributes(
            attributes, device_is_port_path=device_is_port_path,
        ) == (expected, None)
