from urllib.parse import urlencode, quote_plus

from truenas_pylibvirt.device import DisplayDevice

from middlewared.service_exception import ValidationErrors

from .delegate import DeviceDelegate
from .utils import NGINX_PREFIX


class DisplayDelegate(DeviceDelegate):

    RESOLUTION_ENUM = [
        '1920x1200', '1920x1080', '1600x1200', '1600x900',
        '1400x1050', '1280x1024', '1280x720',
        '1024x768', '800x600', '640x480',
    ]

    @staticmethod
    def web_uri(data: dict, host: str, protocol='http'):
        path = DisplayDelegate.get_webui_info(data)['path'][1:]
        params = {'path': path, 'autoconnect': 1}
        get_params = f'?{urlencode(params, quote_via=quote_plus)}'
        return f'{protocol}://{host}/{path}spice_auto.html{get_params}'

    @staticmethod
    def get_webui_info(data: dict) -> dict:
        return {
            'id': data['id'],
            'path': f'{NGINX_PREFIX}/{data["id"]}/',
            'redirect_uri': f'{data["attributes"]["bind"]}:{data["attributes"]["web_port"]}',
        }

    def validate_middleware(
        self,
        device: dict,
        verrors: ValidationErrors,
        old: dict | None = None,
        instance: dict | None = None,
        update: bool = True,
    ) -> None:
        if instance:
            if update:
                # we will remove the device from the list of devices as that reflects db state
                # and not the state of the modified device in question
                instance['devices'] = [
                    d for d in instance['devices']
                    if d.get('id') != device.get('id')
                ]

            instance['devices'].append(device)
            self.middleware.call_sync('vm.device.validate_display_devices', verrors, instance)

        verrors = self.validate_port_attrs(device, verrors)

        if device['attributes']['bind'] not in self.middleware.call_sync('vm.device.bind_choices'):
            verrors.add('attributes.bind', 'Requested bind address is not valid')

    def validate_port_attrs(self, device, verrors=None):
        verrors = ValidationErrors() if verrors is None else verrors
        display_devices_ports = self.middleware.call_sync(
            'vm.all_used_display_device_ports', [['id', '!=', device.get('id') or self.id]]
        )
        new_ports = list((self.middleware.call_sync('vm.port_wizard')).values())
        dev_attrs = device['attributes']
        for port in filter(lambda p: p in new_ports, (dev_attrs.get('port'), dev_attrs.get('web_port'))):
            new_ports.remove(port)

        for key in ('port', 'web_port'):
            if device['attributes'].get(key):
                if not (5900 <= dev_attrs[key] <= 65535):
                    verrors.add(
                        f'attributes.{key}',
                        'Specified port must be between 5900 and 65535, inclusive'
                    )
                if dev_attrs[key] in display_devices_ports:
                    verrors.add(
                        f'attributes.{key}',
                        f'Specified display port({dev_attrs[key]}) is already in use by another Display device'
                    )
                else:
                    verrors.extend(self.middleware.call_sync(
                        'port.validate_port', f'attributes.{key}', dev_attrs[key], dev_attrs['bind'], 'vm.device'
                    ))
            else:
                device['attributes'][key] = new_ports.pop(0)
        return verrors

    def is_available(self, device: DisplayDevice):
        bind_ip_available = device.bind in self.middleware.call_sync('vm.device.bind_choices')
        return bind_ip_available and not self.validate_port_attrs({
            'attributes': device.__dict__
        })
