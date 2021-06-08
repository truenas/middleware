import ipaddress
import psutil

from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str
from middlewared.service import pass_app, Service
from middlewared.validators import MACAddr

from .devices import NIC, DISPLAY


class VMService(Service):

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
        'vmemory_in_use',
        Int('RNP', required=True, description='Running but not provisioned'),
        Int('PRD', required=True, description='Provisioned but not running'),
        Int('RPRD', required=True, description='Running and provisioned'),
    ))
    async def get_vmemory_in_use(self):
        """
        The total amount of virtual memory in MB used by guests

            Returns a dict with the following information:
                RNP - Running but not provisioned
                PRD - Provisioned but not running
                RPRD - Running and provisioned
        """
        memory_allocation = {'RNP': 0, 'PRD': 0, 'RPRD': 0}
        guests = await self.middleware.call('datastore.query', 'vm.vm')
        for guest in guests:
            status = await self.middleware.call('vm.status', guest['id'])
            if status['state'] == 'RUNNING' and guest['autostart'] is False:
                memory_allocation['RNP'] += guest['memory'] * 1024 * 1024
            elif status['state'] == 'RUNNING' and guest['autostart'] is True:
                memory_allocation['RPRD'] += guest['memory'] * 1024 * 1024
            elif guest['autostart']:
                memory_allocation['PRD'] += guest['memory'] * 1024 * 1024

        return memory_allocation

    @accepts(Bool('overcommit', default=False))
    @returns(Int('available_memory'))
    async def get_available_memory(self, overcommit):
        """
        Get the current maximum amount of available memory to be allocated for VMs.

        If `overcommit` is true only the current used memory of running VMs will be accounted for.
        If false all memory (including unused) of runnings VMs will be accounted for.

        This will include memory shrinking ZFS ARC to the minimum.

        Memory is of course a very "volatile" resource, values may change abruptly between a
        second but I deem it good enough to give the user a clue about how much memory is
        available at the current moment and if a VM should be allowed to be launched.
        """
        # Use 90% of available memory to play safe
        free = int(psutil.virtual_memory().available * 0.9)

        # swap used space is accounted for used physical memory because
        # 1. processes (including VMs) can be swapped out
        # 2. we want to avoid using swap
        swap_used = psutil.swap_memory().used * (await self.middleware.call('sysctl.get_pagesize'))

        # Difference between current ARC total size and the minimum allowed
        arc_total = await self.middleware.call('sysctl.get_arcstats_size')
        arc_min = await self.middleware.call('sysctl.get_arc_min')
        arc_shrink = max(0, arc_total - arc_min)

        vms_memory_used = 0
        if overcommit is False:
            # If overcommit is not wanted its verified how much physical memory
            # the vm process is currently using and add the maximum memory its
            # supposed to have.
            for vm in await self.middleware.call('vm.query'):
                status = await self.middleware.call('vm.status', vm['id'])
                if status['pid']:
                    try:
                        p = psutil.Process(status['pid'])
                    except psutil.NoSuchProcess:
                        continue
                    memory_info = p.memory_info()._asdict()
                    memory_info.pop('vms')
                    vms_memory_used += (vm['memory'] * 1024 * 1024) - sum(memory_info.values())

        return max(0, free + arc_shrink - vms_memory_used - swap_used)

    @accepts()
    @returns(Str('mac', validators=[MACAddr(separator=':')]),)
    def random_mac(self):
        """
        Create a random mac address.

        Returns:
            str: with six groups of two hexadecimal digits
        """
        return NIC.random_mac()

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

    @accepts()
    @returns(Dict(
        *[Str(r, enum=[r]) for r in DISPLAY.RESOLUTION_ENUM]
    ))
    async def resolution_choices(self):
        """
        Retrieve supported resolution choices for VM Display devices.
        """
        return {r: r for r in DISPLAY.RESOLUTION_ENUM}
