import psutil
import subprocess

from urllib.parse import urlencode, quote_plus

from middlewared.schema import Bool, Dict, Int, Str
from middlewared.validators import Range

from .device import Device
from .utils import create_element


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

    def web_uri(self, host, password=None):
        params = {} if self.is_spice_type() else {'autoconnect': 1}
        if self.password_configured():
            if password != self.data['attributes'].get('password'):
                return

            params['password'] = password

        get_params = f'?{urlencode(params, quote_via=quote_plus)}' if params else ''

        return f'http://{host}:{self.get_web_port(self.data["attributes"]["port"])}/' \
               f'{"spice_auto" if self.is_spice_type() else "vnc"}.html{get_params}'

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

    def xml_freebsd(self, *args, **kwargs):
        return create_element(
            'controller', type='usb', model='nec-xhci', attribute_dict={
                'children': [create_element('address', type='pci', slot='30')]
            }
        ), create_element('input', type='tablet', bus='usb')

    def hypervisor_args_freebsd(self, *args, **kwargs):
        attrs = self.data['attributes']
        width, height = (attrs.get('resolution') or '1024x768').split('x')
        return '-s ' + ','.join(filter(
            bool, [
                '29',
                'fbuf',
                'vncserver',
                f'tcp={attrs["bind"]}:{attrs["port"]}',
                f'w={width}',
                f'h={height}',
                f'password={attrs["password"]}' if attrs.get('password') else None,
                'wait' if attrs.get('wait') else None,
            ]
        ))

    @staticmethod
    def get_web_port(port):
        split_port = int(str(port)[:2]) - 1
        return int(str(split_port) + str(port)[2:])

    def get_start_attrs(self):
        port = self.data['attributes']['port']
        bind = self.data['attributes']['bind']
        web_port = self.get_web_port(port)
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

    def post_start_vm_freebsd(self, *args, **kwargs):
        start_args = self.get_start_attrs()
        self.web_process = subprocess.Popen(
            [
                '/usr/local/libexec/novnc/utils/websockify/run', '--web', '/usr/local/libexec/novnc/',
                '--wrap-mode=ignore', start_args['web_bind'], start_args['server_addr']
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def post_stop_vm(self, *args, **kwargs):
        if self.web_process and psutil.pid_exists(self.web_process.pid):
            self.middleware.call_sync('service.terminate_process', self.web_process.pid)
        self.web_process = None
