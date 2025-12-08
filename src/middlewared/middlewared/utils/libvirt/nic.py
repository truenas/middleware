import itertools
import random

from middlewared.service_exception import ValidationErrors

from .delegate import DeviceDelegate


class NICDelegate(DeviceDelegate):

    @property
    def nic_choices_endpoint(self):
        raise NotImplementedError()

    @staticmethod
    def random_mac() -> str:
        mac_address = [
            0x00, 0xa0, 0x98, random.randint(0x00, 0x7f), random.randint(0x00, 0xff), random.randint(0x00, 0xff)
        ]
        return ':'.join(['%02x' % x for x in mac_address])

    def validate_middleware(
        self,
        device: dict,
        verrors: ValidationErrors,
        old: dict | None = None,
        instance: dict | None = None,
        update: bool = True,
    ) -> None:
        nic = device['attributes'].get('nic_attach')
        if nic:
            if nic not in itertools.chain(*self.middleware.call_sync(self.nic_choices_endpoint).values()):
                verrors.add('attributes.nic_attach', 'Not a valid choice.')
            elif nic.startswith('br') and device['attributes']['trust_guest_rx_filters']:
                verrors.add(
                    'attributes.trust_guest_rx_filters',
                    'This can only be set when "nic_attach" is not a bridge device'
                )

        # Make sure NIC device has a MAC address
        if not device['attributes'].get('mac'):
            device['attributes']['mac'] = self.random_mac()
