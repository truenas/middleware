from middlewared.common.ports import PortDelegate


class ChartReleasePortDelegate(PortDelegate):

    name = 'applications'
    title = 'Applications'

    async def get_ports(self):
        ports = []
        for chart_release in await self.middleware.call('chart.release.query'):
            for port in chart_release['used_ports']:
                ports.append(port['port'])

        return ports


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', ChartReleasePortDelegate(middleware))
