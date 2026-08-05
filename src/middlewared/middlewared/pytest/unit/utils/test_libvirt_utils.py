import pytest

from middlewared.utils.libvirt.utils import normalize_device_attributes


@pytest.mark.parametrize('attributes,expected', [
    (
        # a modern client sends no `device` at all, so there is nothing to fold in
        {'dtype': 'USB', 'port': '1-4.2'},
        {'dtype': 'USB', 'port': '1-4.2'},
    ),
    (
        {'dtype': 'USB', 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
        {'dtype': 'USB', 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
    ),
    (
        # a legacy name is translated into the port it refers to
        {'dtype': 'USB', 'device': 'usb_5_1_1'},
        {'dtype': 'USB', 'port': '5-1.1'},
    ),
    (
        {'dtype': 'USB', 'device': '1-4.2'},
        {'dtype': 'USB', 'port': '1-4.2'},
    ),
    (
        # an explicit port in the same payload is what the client actually meant
        {'dtype': 'USB', 'device': 'usb_1_4', 'port': '2-1'},
        {'dtype': 'USB', 'port': '2-1'},
    ),
    (
        # switching an old client's device from a port over to an ID pair
        {'dtype': 'USB', 'device': None, 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
    ),
    (
        # a null device on its own still has to clear the port it replaces
        {'dtype': 'USB', 'device': None},
        {'dtype': 'USB', 'port': None},
    ),
    (
        # anything that is not a USB device keeps every key it arrived with
        {'dtype': 'PCI', 'device': 'usb_1_4', 'pptdev': '0000:00:02.0'},
        {'dtype': 'PCI', 'device': 'usb_1_4', 'pptdev': '0000:00:02.0'},
    ),
    (
        {'dtype': 'NIC', 'device': None, 'mac': '00:a0:98:00:00:01'},
        {'dtype': 'NIC', 'device': None, 'mac': '00:a0:98:00:00:01'},
    ),
])
def test_normalize_device_attributes(attributes, expected):
    assert normalize_device_attributes(attributes) == expected
