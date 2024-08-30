from socket import AF_INET6

from middlewared.schema import accepts, Dict, Int, List, returns, Str
from middlewared.service import pass_app, private, Service

from .devices import DISPLAY
from .utils import NGINX_PREFIX


class VMService(Service):

    @accepts(roles=['VM_READ'])
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
        all_ports = await self.middleware.call('port.get_all_used_ports')

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

    @accepts(Int('id'), roles=['VM_READ'])
    @returns(List(
        'vmdevice', items=[
            Dict(
                'vmdevice',
                Int('id'),
                Str('dtype'),
                DISPLAY.schema,
                Int('order'),
                Int('vm'),
            ),
        ]
    ))
    async def get_display_devices(self, id_):
        """
        Get the display devices from a given guest. If a display device has password configured,
        `attributes.password_configured` will be set to `true`.
        """
        devices = []
        for device in await self.middleware.call('vm.device.query', [['vm', '=', id_], ['dtype', '=', 'DISPLAY']]):
            device['attributes']['password_configured'] = bool(device['attributes'].get('password'))
            devices.append(device)
        return devices

    @accepts(
        Int('id'),
        Str('host', default=''),
        Dict(
            'options',
            Str('protocol', default='HTTP', enum=['HTTP', 'HTTPS']),
        ),
        roles=['VM_READ']
    )
    @returns(Dict(
        'display_devices_uri',
        Str('error', null=True),
        Str('uri', null=True),
    ))
    @pass_app()
    async def get_display_web_uri(self, app, id_, host, options):
        """
        Retrieve Display URI for a given VM or appropriate error if there is no display device available
        or if it is not configured to use web interface
        """
        uri_data = {'error': None, 'uri': None}
        protocol = options['protocol'].lower()
        if not host:
            try:
                if app.origin.is_tcp_ip_family and (_h := app.origin.loc_addr):
                    host = _h
                    if app.origin.family == AF_INET6:
                        host = f'[{_h}]'
            except AttributeError:
                pass

        if display_devices := await self.get_display_devices(id_):
            for device in map(lambda d: DISPLAY(d, middleware=self.middleware), display_devices):
                if device.data['attributes'].get('web'):
                    uri_data['uri'] = device.web_uri(host, protocol=protocol)
                else:
                    uri_data['error'] = 'Web display is not configured'
        else:
            uri_data['error'] = 'Display device is not configured for this VM'

        return uri_data

    @private
    async def get_display_devices_ui_info(self):
        devices = []
        for device in await self.middleware.call('vm.device.query', [['dtype', '=', 'DISPLAY']]):
            devices.append(DISPLAY(device, middleware=self.middleware).get_webui_info())
        return devices

    @private
    async def get_vm_display_nginx_route(self):
        return NGINX_PREFIX
