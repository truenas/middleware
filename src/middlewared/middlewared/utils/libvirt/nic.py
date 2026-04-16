import itertools
import random

from typing import Any

from middlewared.service_exception import ValidationErrors

from .delegate import DeviceDelegate
from .factory_utils import is_bridge_device
from .utils import device_uniqueness_check


class NICDelegate(DeviceDelegate):

    @property
    def nic_choices_endpoint(self) -> str:
        raise NotImplementedError()

    @staticmethod
    def random_mac() -> str:
        mac_address = [
            0x00, 0xa0, 0x98, random.randint(0x00, 0x7f), random.randint(0x00, 0xff), random.randint(0x00, 0xff)
        ]
        return ':'.join(['%02x' % x for x in mac_address])

    def validate_middleware(
        self,
        device: dict[str, Any],
        verrors: ValidationErrors,
        old: dict[str, Any] | None = None,
        instance: dict[str, Any] | None = None,
        update: bool = True,
    ) -> None:
        nic = device['attributes'].get('nic_attach')
        if nic:
            choices = self.middleware.call_sync(self.nic_choices_endpoint).model_dump()
            if nic not in itertools.chain(*choices.values()):
                verrors.add('attributes.nic_attach', 'Not a valid choice.')
            elif is_bridge_device(nic) and device['attributes']['trust_guest_rx_filters']:
                verrors.add(
                    'attributes.trust_guest_rx_filters',
                    'This can only be set when "nic_attach" is not a bridge device'
                )

        # Make sure NIC device has a MAC address
        if not device['attributes'].get('mac'):
            device['attributes']['mac'] = self.random_mac()

        if instance is not None and device['attributes'].get('mac') and not device_uniqueness_check(
            device, instance, 'NIC',
        ):
            verrors.add(
                'attributes.mac',
                f'{instance["name"]} already has a NIC with MAC address {device["attributes"]["mac"]!r} configured'
            )
