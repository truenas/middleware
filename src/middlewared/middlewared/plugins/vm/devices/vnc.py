import os
import psutil
import signal
import subprocess

from middlewared.schema import Bool, Dict, Int, Str
from middlewared.validators import Range

from .device import Device
from .utils import create_element


class VNC(Device):

    schema = Dict(
        'attributes',
        Str('vnc_resolution', enum=[
            '1920x1200', '1920x1080', '1600x1200', '1600x900',
            '1400x1050', '1280x1024', '1280x720',
            '1024x768', '800x600', '640x480',
        ], default='1024x768'),
        Int('vnc_port', default=None, null=True, validators=[Range(min=5900, max=65535)]),
        Str('vnc_bind', default='0.0.0.0'),
        Bool('wait', default=False),
        Str('vnc_password', default=None, null=True, private=True),
        Bool('vnc_web', default=False),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.web_process = None

    def xml_linux(self, *args, **kwargs):
        # TODO: Unable to set resolution for VNC devices
        attrs = self.data['attributes']
        return create_element(
            'graphics', type='vnc', port=str(self.data['attributes']['vnc_port']), attribute_dict={
                'children': [
                    create_element('listen', type='address', address=self.data['attributes']['vnc_bind']),
                ]
            }, **({} if not attrs['vnc_password'] else {'passwd': attrs['vnc_password']})
        )

    def xml_freebsd(self, *args, **kwargs):
        return create_element(
            'controller', type='usb', model='nec-xhci', attribute_dict={
                'children': [create_element('address', type='pci', slot='30')]
            }
        ), create_element('input', type='tablet', bus='usb')

    def hypervisor_args_freebsd(self, *args, **kwargs):
        attrs = self.data['attributes']
        width, height = (attrs['vnc_resolution'] or '1024x768').split('x')
        return '-s ' + ','.join(filter(
            bool, [
                '29',
                'fbuf',
                'vncserver',
                f'tcp={attrs["vnc_bind"]}:{attrs["vnc_port"]}',
                f'w={width}',
                f'h={height}',
                f'password={attrs["vnc_password"]}' if attrs['vnc_password'] else None,
                'wait' if attrs.get('wait') else None,
            ]
        ))

    @staticmethod
    def get_vnc_web_port(vnc_port):
        split_port = int(str(vnc_port)[:2]) - 1
        return int(str(split_port) + str(vnc_port)[2:])

    def get_start_attrs(self):
        vnc_port = self.data['attributes']['vnc_port']
        vnc_bind = self.data['attributes']['vnc_bind']
        vnc_web_port = self.get_vnc_web_port(vnc_port)
        return {
            'web_bind': f':{vnc_web_port}' if vnc_bind == '0.0.0.0' else f'{vnc_bind}:{vnc_web_port}',
            'server_addr': f'{vnc_bind}:{vnc_port}'
        }

    def post_start_vm_linux(self, *args, **kwargs):
        start_args = self.get_start_attrs()
        self.web_process = subprocess.Popen(
            [
                'websockify', '--web', '/usr/share/novnc/', '--wrap-mode=ignore',
                start_args['web_bind'], start_args['server_addr']
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
            if self.middleware:
                self.middleware.call_sync('service.terminate_process', self.web_process.pid)
            else:
                os.kill(self.web_process.pid, signal.SIGKILL)
        self.web_process = None
