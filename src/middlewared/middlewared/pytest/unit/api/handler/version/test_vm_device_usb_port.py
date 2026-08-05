import pytest

from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.api.v25_04_2.vm_device import VMDeviceCreateArgs as VMDeviceCreateArgs_v25_04_2
from middlewared.api.v25_10_0.vm_device import VMDeviceCreateArgs as VMDeviceCreateArgs_v25_10_0
from middlewared.api.v25_10_1.vm_device import VMDeviceCreateArgs as VMDeviceCreateArgs_v25_10_1
from middlewared.api.v25_10_2.vm_device import VMDeviceCreateArgs as VMDeviceCreateArgs_v25_10_2
from middlewared.api.v25_10_3.vm_device import VMDeviceCreateArgs as VMDeviceCreateArgs_v25_10_3
from middlewared.api.v25_10_4.vm_device import VMDeviceCreateArgs as VMDeviceCreateArgs_v25_10_4
from middlewared.api.v25_10_5.vm_device import VMDeviceCreateArgs as VMDeviceCreateArgs_v25_10_5
from middlewared.api.v26_0_0.vm_device import VMDeviceCreateArgs as VMDeviceCreateArgs_v26_0_0

from .utils import TestModelProvider


OLDEST_VERSION = 'v25.04.2'
CURRENT_VERSION = 'v26.0.0'

_MODELS_BY_VERSION = {
    OLDEST_VERSION: VMDeviceCreateArgs_v25_04_2,
    'v25.10.0': VMDeviceCreateArgs_v25_10_0,
    'v25.10.1': VMDeviceCreateArgs_v25_10_1,
    'v25.10.2': VMDeviceCreateArgs_v25_10_2,
    'v25.10.3': VMDeviceCreateArgs_v25_10_3,
    'v25.10.4': VMDeviceCreateArgs_v25_10_4,
    'v25.10.5': VMDeviceCreateArgs_v25_10_5,
    CURRENT_VERSION: VMDeviceCreateArgs_v26_0_0,
}


def _build_adapter():
    return APIVersionsAdapter([
        APIVersion(version, TestModelProvider({'VMDeviceCreateArgs': model}))
        for version, model in _MODELS_BY_VERSION.items()
    ])


async def _adapt(attributes, version1, version2):
    adapter = _build_adapter()
    value = {'vm_device_create': {'attributes': attributes, 'vm': 1, 'order': None}}
    adapted = await adapter.adapt(value, 'VMDeviceCreateArgs', version1, version2)
    return adapted['vm_device_create']['attributes']


@pytest.mark.asyncio
@pytest.mark.parametrize('device,expected_port', [
    ('usb_1_4_2', '1-4.2'),
    ('usb_1_4', '1-4'),
    ('usb_5_1_1', '5-1.1'),
    # Already a port path: the transform is idempotent.
    ('3-2', '3-2'),
])
async def test_upgrade_turns_device_into_port(device, expected_port):
    attributes = await _adapt(
        {'dtype': 'USB', 'device': device, 'usb': None, 'controller_type': 'nec-xhci'},
        OLDEST_VERSION,
        CURRENT_VERSION,
    )

    assert attributes['port'] == expected_port
    assert 'device' not in attributes


@pytest.mark.asyncio
async def test_upgrade_keeps_ids_when_no_device_is_set():
    attributes = await _adapt(
        {
            'dtype': 'USB',
            'device': None,
            'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'},
            'controller_type': 'nec-xhci',
        },
        OLDEST_VERSION,
        CURRENT_VERSION,
    )

    assert attributes['port'] is None
    assert attributes['usb'] == {'vendor_id': '0x1d6b', 'product_id': '0x0002'}
    assert 'device' not in attributes


@pytest.mark.asyncio
@pytest.mark.parametrize('vendor_id,product_id,expected', [
    ('0xABCD', '0x1234', {'vendor_id': '0xabcd', 'product_id': '0x1234'}),
    ('0xabc', '0x2', {'vendor_id': '0x0abc', 'product_id': '0x0002'}),
])
async def test_upgrade_normalizes_loosely_formatted_ids(vendor_id, product_id, expected):
    """Pre-26 clients were allowed any `0x`-prefixed id, so uppercase and short forms must survive."""
    attributes = await _adapt(
        {
            'dtype': 'USB',
            'device': None,
            'usb': {'vendor_id': vendor_id, 'product_id': product_id},
            'controller_type': 'nec-xhci',
        },
        OLDEST_VERSION,
        CURRENT_VERSION,
    )

    assert attributes['usb'] == expected
    assert attributes['port'] is None


@pytest.mark.asyncio
async def test_downgrade_turns_port_into_device():
    attributes = await _adapt(
        {'dtype': 'USB', 'port': '1-4.2', 'usb': None, 'controller_type': 'nec-xhci'},
        CURRENT_VERSION,
        OLDEST_VERSION,
    )

    assert attributes['device'] == '1-4.2'
    assert 'port' not in attributes


@pytest.mark.asyncio
async def test_downgrade_keeps_ids_when_no_port_is_set():
    attributes = await _adapt(
        {
            'dtype': 'USB',
            'port': None,
            'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'},
            'controller_type': 'nec-xhci',
        },
        CURRENT_VERSION,
        OLDEST_VERSION,
    )

    assert attributes['device'] is None
    assert attributes['usb'] == {'vendor_id': '0x1d6b', 'product_id': '0x0002'}
    assert 'port' not in attributes
