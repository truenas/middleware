from middlewared.common.ports import PortDelegate


class ChartReleasePortDelegate(PortDelegate):

    name = 'applications'
    namespace = 'chart.release'
    title = 'Applications'

    async def get_ports(self):
        ports = []
        for chart_release in await self.middleware.call('chart.release.query'):
            chart_release_ports = []
            for port in chart_release['used_ports']:
                chart_release_ports.append(port['port'])

            ports.append({
                'description': f'{chart_release["id"]!r} application',
                'ports': chart_release_ports,
            })

        return ports


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', ChartReleasePortDelegate(middleware))
