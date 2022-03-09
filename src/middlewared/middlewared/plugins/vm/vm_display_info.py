import ipaddress

from middlewared.schema import accepts, Dict, Int, List, Ref, returns, Str
from middlewared.service import pass_app, private, Service

from .devices import DISPLAY


class VMService(Service):

    @accepts()
    @returns(Dict(
        'available_display_port',
        Int('port', required=True, description='Available server port'),
        Int('web', required=True, description='Web port to be used based on available `port`'),
    ))
    async def port_wizard(self):
        """
        It returns the next available Display Server Port and Web Port.

        Returns a dict with two keys `port` and `web`.
        """
        all_ports = [
            d['attributes'].get('port')
            for d in (await self.middleware.call('vm.device.query', [['dtype', '=', 'DISPLAY']]))
        ] + [6000, 6100]

        port = next((i for i in range(5900, 65535) if i not in all_ports))
        return {'port': port, 'web': DISPLAY.get_web_port(port)}

    @accepts()
    @returns(Dict(
        *[Str(r, enum=[r]) for r in DISPLAY.RESOLUTION_ENUM]
    ))
    async def resolution_choices(self):
        """
        Retrieve supported resolution choices for VM Display devices.
        """
        return {r: r for r in DISPLAY.RESOLUTION_ENUM}

    @accepts(Int('id'))
    @returns(List(items=[Ref('vm_device_entry')]))
    async def get_display_devices(self, id):
        """
        Get the display devices from a given guest. If a display device has password configured,
        `attributes.password_configured` will be set to `true`.
        """
        devices = []
        for device in await self.middleware.call('vm.device.query', [['vm', '=', id], ['dtype', '=', 'DISPLAY']]):
            device['attributes']['password_configured'] = bool(device['attributes'].get('password'))
            devices.append(device)
        return devices

    @accepts(
        Int('id'),
        Str('host', default=''),
        Dict(
            'options',
            List('devices_passwords', items=[Dict(
                'device_password',
                Int('device_id', required=True),
                Str('password', required=True, empty=False))
            ])
        )
    )
    @returns(Dict('display_devices_uri', additional_attrs=True))
    @pass_app()
    async def get_display_web_uri(self, app, id, host, options):
        """
        Retrieve Display URI's for a given VM.

        Display devices which have a password configured must specify the password explicitly to retrieve display
        device web uri. In case a password is not specified, the uri for display device in question will not be
        retrieved because of missing password information.
        """
        web_uris = {}

        host = host or await self.middleware.call('interface.websocket_local_ip', app=app)
        try:
            ipaddress.IPv6Address(host)
        except ipaddress.AddressValueError:
            pass
        else:
            host = f'[{host}]'

        creds = {d['device_id']: d['password'] for d in options['devices_passwords']}
        for device in map(lambda d: DISPLAY(d, middleware=self.middleware), await self.get_display_devices(id)):
            uri_data = {'error': None, 'uri': None}
            if device.data['attributes'].get('web'):
                if device.password_configured():
                    if creds.get(
                        device.data['id']
                    ) and creds[device.data['id']] != device.data['attributes']['password']:
                        uri_data['error'] = 'Incorrect password specified'
                    elif not creds.get(device.data['id']):
                        uri_data['error'] = 'Password not specified'

                uri_data['uri'] = device.web_uri(host, creds.get(device.data['id']))
            else:
                uri_data['error'] = 'Web display is not configured'
            web_uris[device.data['id']] = uri_data
        return web_uris

    @private
    async def get_running_display_devices(self):
        devices = []
        for vm in await self.middleware.call('vm.query', [['status.state', '=', 'RUNNING']]):
            devices.extend([
                dev.get_webui_info() for dev in map(
                    lambda d: DISPLAY(d, middleware=self.middleware),
                    filter(lambda d: d['dtype'] == 'DISPLAY', vm['devices'])
                )
            ])
        return devices
