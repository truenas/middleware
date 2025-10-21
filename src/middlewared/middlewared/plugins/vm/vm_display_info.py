from socket import AF_INET6

from middlewared.api import api_method
from middlewared.api.current import (
    VMPortWizardArgs, VMPortWizardResult, VMResolutionChoicesArgs, VMResolutionChoicesResult, VMGetDisplayDevicesArgs,
    VMGetDisplayDevicesResult, VMGetDisplayWebUriArgs, VMGetDisplayWebUriResult,
)
from middlewared.service import pass_app, private, Service
from middlewared.utils.libvirt.display import DisplayDelegate, NGINX_PREFIX


class VMService(Service):

    @api_method(VMPortWizardArgs, VMPortWizardResult, roles=['VM_READ'])
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
        for device in await self.middleware.call(
            'vm.device.query', [['attributes.dtype', '=', 'DISPLAY']] + additional_filters
        ):
            all_ports.extend([device['attributes']['port'], device['attributes']['web_port']])
        return all_ports

    @api_method(VMResolutionChoicesArgs, VMResolutionChoicesResult, roles=['VM_READ'])
    async def resolution_choices(self):
        """
        Retrieve supported resolution choices for VM Display devices.
        """
        return {r: r for r in DisplayDelegate.RESOLUTION_ENUM}

    @api_method(VMGetDisplayDevicesArgs, VMGetDisplayDevicesResult, roles=['VM_READ'])
    async def get_display_devices(self, id_):
        """
        Get the display devices from a given guest. If a display device has password configured,
        `attributes.password_configured` will be set to `true`.
        """
        devices = []
        for device in await self.middleware.call(
            'vm.device.query', [['vm', '=', id_], ['attributes.dtype', '=', 'DISPLAY']]
        ):
            device['attributes']['password_configured'] = bool(device['attributes'].get('password'))
            devices.append(device)
        return devices

    @api_method(VMGetDisplayWebUriArgs, VMGetDisplayWebUriResult, roles=['VM_READ'])
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
            for device_data in display_devices:
                if device_data['attributes'].get('web'):
                    uri_data.update({
                        'uri': DisplayDelegate.web_uri(device_data, host, protocol=protocol),
                        'error': None,
                    })
                    break
                else:
                    uri_data['error'] = 'Web display is not configured'
        else:
            uri_data['error'] = 'Display device is not configured for this VM'

        return uri_data

    @private
    async def get_vm_display_nginx_route(self):
        return NGINX_PREFIX
