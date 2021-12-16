from middlewared.service import Service, private, periodic
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

    @periodic(86400, run_on_start=False)
    @private
    def retrieve_logs(self):
        events = await self.middleware.call('hardare.events.report')
        if events['MCA_EVENTS'] or events['APEI_EVENTS']:
            # we need to keep a paper-trail of these since the msgbuf
            # is circular and can be (and will be) rolled over
            self.logger.warning('Detected MCA and/or APEI events: %s', events)

            serial = await self.middleware.call('system.dmidecode_info')['system-serial-number']
            info = {
                'title': f'MCA or APEI event(s) detected on system with serial: ({serial})',
                'body': f'Detected event(s): {events!r}',
                'attach_debug': True,
                'category': 'Hardware',
                'criticality': 'Potential loss of functionality',
                'environment': 'Production',
                'name': 'Automatic Alert',
                'email': 'auto-support@ixsystems.com',
                'phone': '-',
            }
            job = await self.middleware.call('support.new_ticket', info)
            await job.wait()
            if job.error:
                self.logger.warning('Failed to generate proactive ticket for MCA/APEI event(s): %r', job.error)
