import subprocess

from urllib.parse import urlencode, quote_plus

from middlewared.api.current import VMDisplayDevice
from middlewared.schema import Dict, ValidationErrors
from middlewared.utils.os import get_pids

from .device import Device
from .utils import create_element, NGINX_PREFIX


class DISPLAY(Device):

    RESOLUTION_ENUM = [
        '1920x1200', '1920x1080', '1600x1200', '1600x900',
        '1400x1050', '1280x1024', '1280x720',
        '1024x768', '800x600', '640x480',
    ]

    schema = Dict(
        'attributes',
    )
    schema_model = VMDisplayDevice

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.web_process = None

    def identity(self):
        data = self.data['attributes']
        return f'{data["bind"]}:{data["port"]}'

    def is_spice_type(self):
        return self.data['attributes']['type'] == 'SPICE'

    def web_uri(self, host, protocol='http'):
        path = self.get_webui_info()['path'][1:]
        params = {'path': path, 'autoconnect': 1}
        get_params = f'?{urlencode(params, quote_via=quote_plus)}'
        return f'{protocol}://{host}/{path}spice_auto.html{get_params}'

    def is_available(self):
        bind_ip_available = self.data['attributes']['bind'] in self.middleware.call_sync('vm.device.bind_choices')
        return bind_ip_available and not self.validate_port_attrs(self.data)

    def resolution(self):
        return self.data['attributes']['resolution']

    def xml(self, *args, **kwargs):
        # FIXME: Resolution is not respected when we have more then 1 display device as we are not able to bind
        #  video element to a graphic element
        attrs = self.data['attributes']
        return create_element(
            'graphics', type='spice' if self.is_spice_type() else 'vnc', port=str(self.data['attributes']['port']),
            attribute_dict={
                'children': [
                    create_element('listen', type='address', address=self.data['attributes']['bind']),
                ]
            }, **({} if not attrs['password'] else {'passwd': attrs['password']})
        ), create_element(
            'controller', type='usb', model='nec-xhci'
        ), create_element('input', type='tablet', bus='usb'), create_element('video', attribute_dict={
            'children': [
                create_element('model', type='qxl', attribute_dict={
                    'children': [create_element(
                        'resolution', x=self.resolution().split('x')[0], y=self.resolution().split('x')[-1]
                    )]
                }, vgamem=str(64*1024), ram=str(128*1024), vram=str(64*1024))
            ]
        })

    def get_start_attrs(self):
        port = self.data['attributes']['port']
        bind = self.data['attributes']['bind']
        web_port = self.data['attributes']['web_port']
        return {
            'web_bind': f':{web_port}' if bind == '0.0.0.0' else f'{bind}:{web_port}',
            'server_addr': f'{bind}:{port}'
        }

    def post_start_vm(self, *args, **kwargs):
        start_args = self.get_start_attrs()
        if self.is_spice_type():
            self.web_process = subprocess.Popen(
                [
                    'websockify', '--web', '/usr/share/spice-html5/',
                    '--wrap-mode=ignore', start_args['web_bind'], start_args['server_addr']
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

    def post_stop_vm(self, *args, **kwargs):
        if self.web_process:
            for proc in filter(lambda x: x and x.pid == self.web_process.pid, get_pids()):
                proc.terminate()
        self.web_process = None

    def get_webui_info(self):
        return {
            'id': self.data['id'],
            'path': f'{NGINX_PREFIX}/{self.data["id"]}/',
            'redirect_uri': f'{self.data["attributes"]["bind"]}:'
                            f'{self.data["attributes"]["web_port"]}',
        }

    def _validate(self, device, verrors, old=None, vm_instance=None, update=True):
        if vm_instance:
            if update:
                # we will remove the device from the list of devices as that reflects db state
                # and not the state of the modified device in question
                vm_instance['devices'] = [
                    d for d in vm_instance['devices']
                    if d.get('id') != device.get('id')
                ]

            vm_instance['devices'].append(device)
            self.middleware.call_sync('vm.device.validate_display_devices', verrors, vm_instance)

        password = device['attributes']['password']
        if not password or not password.strip():
            verrors.add('attributes.password', 'Password is required for display devices')

        if device['attributes']['type'] == 'VNC':
            if device['attributes']['web'] is True:
                verrors.add(
                    'attributes.web',
                    'Web access is not supported for VNC display devices, please use SPICE instead'
                )
            if password and len(password) > 8:
                # libvirt error otherwise i.e
                # libvirt.libvirtError: unsupported configuration: VNC password is 11 characters long, only 8 permitted
                verrors.add(
                    'attributes.password',
                    'Password for VNC display devices must be 8 characters or less'
                )

        verrors = self.validate_port_attrs(device, verrors)

        if device['attributes']['bind'] not in self.middleware.call_sync('vm.device.bind_choices'):
            verrors.add('attributes.bind', 'Requested bind address is not valid')

    def validate_port_attrs(self, device, verrors=None):
        verrors = ValidationErrors() if verrors is None else verrors
        display_devices_ports = self.middleware.call_sync(
            'vm.all_used_display_device_ports', [['id', '!=', device.get('id')]]
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
