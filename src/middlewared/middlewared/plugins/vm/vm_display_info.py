import ipaddress
import itertools

from middlewared.schema import accepts, Dict, Int, List, Ref, returns, Str
from middlewared.service import pass_app, private, Service

from .devices import DISPLAY
from .utils import ACTIVE_STATES, NGINX_PREFIX


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
        all_ports = list(itertools.chain(
            *[entry['ports'] for entry in await self.middleware.call('port.get_in_use')]
        ))

        def get_next_port():
            for i in filter(lambda i: i not in all_ports, range(5900, 65535)):
                yield i

        gen = get_next_port()
        return {'port': next(gen), 'web': next(gen)}

    @private
    async def all_used_display_device_ports(self, additional_filters=None):
        all_ports = [6000]
        additional_filters = additional_filters or []
        for device in await self.middleware.call('vm.device.query', [['dtype', '=', 'DISPLAY']] + additional_filters):
            all_ports.extend([device['attributes']['port'], device['attributes']['web_port']])
        return all_ports

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
            ]),
            Str('protocol', default='HTTP', enum=['HTTP', 'HTTPS']),
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
        protocol = options['protocol'].lower()
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

                uri_data['uri'] = device.web_uri(host, creds.get(device.data['id']), protocol)
            else:
                uri_data['error'] = 'Web display is not configured'
            web_uris[device.data['id']] = uri_data
        return web_uris

    @private
    async def get_running_display_devices(self):
        # TODO: Verify how to handle paused vms wrt display devices
        devices = []
        for vm in await self.middleware.call('vm.query', [['status.state', 'in', ACTIVE_STATES]]):
            devices.extend([
                dev.get_webui_info() for dev in map(
                    lambda d: DISPLAY(d, middleware=self.middleware),
                    filter(lambda d: d['dtype'] == 'DISPLAY', vm['devices'])
                )
            ])
        return devices

    @private
    async def get_vm_display_nginx_route(self):
        return NGINX_PREFIX

    @private
    async def get_haproxy_uri(self):
        return 'localhost:700'
