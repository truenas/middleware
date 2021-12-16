from middlewared.service import Service
from middlewared.schema import accepts, returns, Dict, List, Str


class HardwareEventsService(Service):

    class Config:
        namespace = 'hardware.events'

    @accepts()
    @returns(List('mca_events', items=[Str('mca_event')]))
    async def mca(self):
        return (await self.middleware.call('hardware.report'))['MCA_EVENTS']

    @accepts()
    @returns(List('apei_events', items=[Dict('apei_event', additional_attrs=True)]))
    async def apei(self):
        return (await self.middleware.call('hardware.report'))['APEI_EVENTS']

    @accepts()
    @returns(Dict(
        'events',
        List('mca_events', items=[Str('mca_event')]),
        List('mca_events', items=[Dict('apei_event', additional_attrs=True)])
    ))
    async def report(self):
        return await self.middleware.call('hardware.report')
