import pytest

from middlewared.plugins.vm.devices import NIC
from middlewared.pytest.unit.middleware import Middleware

from middlewared.service_exception import ValidationErrors


AVAILABLE_NIC_INTERFACES = ['br0', 'eth0']


@pytest.mark.parametrize('device_data,expected_error', [
    (
        {
            'attributes': {
                'type': 'VIRTIO',
                'mac': '00:a0:99:7e:bb:8a',
                'nic_attach': 'br0',
                'trust_guest_rx_filters': False,
                'dtype': 'NIC',
            },
        },
        ''
    ),
    (
        {
            'attributes': {
                'type': 'VIRTIO',
                'mac': '00:a0:99:7e:bb:8a',
                'nic_attach': 'br2',
                'dtype': 'NIC',
                'trust_guest_rx_filters': False
            },
        },
        '[EINVAL] attributes.nic_attach: Not a valid choice.'
    ),
    (
        {
            'attributes': {
                'type': 'VIRTIO',
                'mac': 'ff:a0:99:7e:bb:8a',
                'nic_attach': 'br0',
                'dtype': 'NIC',
                'trust_guest_rx_filters': False
            },
        },
        '[EINVAL] attributes.mac: MAC address must not start with `ff`'
    ),
    (
        {
            'attributes': {
                'type': 'VIRTIO',
                'mac': 'ff:a0:99:7e:bb:8a',
                'nic_attach': 'br0',
                'dtype': 'NIC',
                'trust_guest_rx_filters': True
            },
        },
        '[EINVAL] attributes.trust_guest_rx_filters: This can only be set when "nic_attach" is not a bridge device'
    ),
    (
        {
            'attributes': {
                'type': 'E1000',
                'mac': 'ff:a0:99:7e:bb:8a',
                'nic_attach': 'eth0',
                'dtype': 'NIC',
                'trust_guest_rx_filters': True
            },
        },
        '[EINVAL] attributes.trust_guest_rx_filters: This can only be set when "type" of NIC device is "VIRTIO"'
    ),
])
def test_nic_device_validation(device_data, expected_error):
    m = Middleware()
    m['vm.device.nic_attach_choices'] = lambda *arg: AVAILABLE_NIC_INTERFACES
    if expected_error:
        with pytest.raises(ValidationErrors) as ve:
            NIC(device_data, m).validate(device_data)

        assert str(ve.value.errors[0]) == expected_error
    else:
        assert NIC(device_data, m).validate(device_data) is None
