import re

import pytest

from truenas_api_client import ValidationErrors
from middlewared.test.integration.utils import call


USB_PORT_RE = re.compile(r'^\d+-\d+(\.\d+)*$')


def _create_usb_device(attributes):
    # The VM does not have to exist: the attributes are validated by the API before the method
    # body ever looks the VM up, which keeps this test free of any VM or USB hardware.
    call('vm.device.create', {'vm': 1, 'attributes': {'dtype': 'USB', **attributes}})


@pytest.mark.parametrize('attributes', [
    # Both identities at once.
    {'port': '1-4', 'usb': {'vendor_id': '0x1d6b', 'product_id': '0x0002'}},
    # Neither identity.
    {'port': None, 'usb': None},
    {},
])
def test_usb_device_requires_exactly_one_identity(attributes):
    with pytest.raises(ValidationErrors) as ve:
        _create_usb_device(attributes)

    assert any(
        'Exactly one of `port` or `usb` must be specified' in error.errmsg
        for error in ve.value.errors
    ), ve.value.errors


@pytest.mark.parametrize('port', ['usb_1_4', '1', '1-', 'not-a-port', '1-4.'])
def test_usb_device_rejects_malformed_port(port):
    with pytest.raises(ValidationErrors) as ve:
        _create_usb_device({'port': port})

    assert any(error.attribute.endswith('port') for error in ve.value.errors), ve.value.errors


def test_usb_passthrough_choices_are_keyed_by_port():
    for port in call('vm.device.usb_passthrough_choices'):
        assert USB_PORT_RE.match(port), port
