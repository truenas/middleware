from datetime import timedelta

from middlewared.alert.base import AlertSource
from middlewared.alert.schedule import IntervalSchedule


class MCAAlertSource(AlertSource):
    products = ('ENTERPRISE',)
    schedule = IntervalSchedule(timedelta(hours=24))

    async def check(self):
        """
        This is using the alert infrastructure solely for running
        at a given interval. We do not raise an alert to the end-user
        at this time and only generate a proactive ticket that gets
        sent to the support team. Also this runs for anyone that has
        enterprise hardware and not just Gold customers. This is at
        the request of the PM team.
        """
        events = await self.middleware.call('hardare.events.report')
        if events['MCA_EVENTS'] or events['APEI_EVENTS']:
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
                self.logger.warning(f'Failed to generate proactive ticket for MCA/APEI event(s): {job.error!r}')
