from middlewared.common.ports import PortDelegate


class AppPortDelegate(PortDelegate):

    name = 'applications'
    namespace = 'app'
    title = 'Applications'

    async def get_ports(self):
        ports = []
        for app in filter(
            lambda a: a['active_workloads']['used_ports'],
            await self.middleware.call('app.query')
        ):
            app_ports = []
            for port_entry in app['active_workloads']['used_ports']:
                for host_port in port_entry['host_ports']:
                    app_ports.append(('0.0.0.0', host_port['host_port']))

            ports.append({
                'description': f'{app["id"]!r} application',
                'ports': app_ports,
            })

        return ports


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', AppPortDelegate(middleware))
