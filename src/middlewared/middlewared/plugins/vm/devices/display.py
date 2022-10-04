import psutil
import subprocess

from urllib.parse import urlencode, quote_plus

from middlewared.schema import Bool, Dict, Int, Str
from middlewared.validators import Range

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
        Str('resolution', enum=RESOLUTION_ENUM, default='1024x768'),
        Int('port', default=None, null=True, validators=[Range(min=5900, max=65535)]),
        Int('web_port', default=None, null=True, validators=[Range(min=5900, max=65535)]),
        Str('bind', default='0.0.0.0'),
        Bool('wait', default=False),
        Str('password', default=None, null=True, private=True),
        Bool('web', default=True),
        Str('type', default='SPICE', enum=['SPICE', 'VNC']),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.web_process = None

    def identity(self):
        data = self.data['attributes']
        return f'{data["bind"]}:{data["port"]}'

    def is_spice_type(self):
        return self.data['attributes']['type'] == 'SPICE'

    def password_configured(self):
        return bool(self.data['attributes'].get('password'))

    def web_uri(self, host, password=None, protocol='http'):
        path = self.get_webui_info()['path'][1:]
        params = {'path': path, 'autoconnect': 1}
        if self.password_configured():
            if password != self.data['attributes'].get('password'):
                return

            params['password'] = password

        get_params = f'?{urlencode(params, quote_via=quote_plus)}'
        return f'{protocol}://{host}/{path}{"spice_auto" if self.is_spice_type() else "vnc"}.html{get_params}'

    def is_available(self):
        return self.data['attributes']['bind'] in self.middleware.call_sync('vm.device.bind_choices')

    def resolution(self):
        return self.data['attributes']['resolution']

    def xml_linux(self, *args, **kwargs):
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
                })
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

    def post_start_vm_linux(self, *args, **kwargs):
        start_args = self.get_start_attrs()
        self.web_process = subprocess.Popen(
            [
                'websockify', '--web', f'/usr/share/{"spice-html5" if self.is_spice_type() else "novnc"}/',
                '--wrap-mode=ignore', start_args['web_bind'], start_args['server_addr']
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def post_stop_vm(self, *args, **kwargs):
        if self.web_process and psutil.pid_exists(self.web_process.pid):
            self.middleware.call_sync('service.terminate_process', self.web_process.pid)
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
            if not update:
                vm_instance['devices'].append(device)

            self.middleware.call_sync('vm.device.validate_display_devices', verrors, vm_instance)

        display_devices_ports = self.middleware.call_sync(
            'vm.all_used_display_device_ports', [['id', '!=', device.get('id')]]
        )
        new_ports = list((self.middleware.call_sync('vm.port_wizard')).values())
        for key in ('port', 'web_port'):
            if device['attributes'].get(key):
                if device['attributes'][key] in display_devices_ports:
                    verrors.add(
                        f'attributes.{key}',
                        'Specified display port is already in use by another Display device'
                    )
                else:
                    verrors.extend(self.middleware.call_sync(
                        'port.validate_port', f'attributes.{key}', device['attributes'][key], 'vm.device'
                    ))
            else:
                device['attributes'][key] = new_ports.pop(0)

        if device['attributes']['bind'] not in self.middleware.call_sync('vm.device.bind_choices'):
            verrors.add('attributes.bind', 'Requested bind address is not valid')
