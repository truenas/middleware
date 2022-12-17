import asyncio
import time

from middlewared.event import EventSource
from middlewared.service import private, Service
from middlewared.service_exception import MatchNotFound


class SMARTTestService(Service):

    class Config:
        namespace = 'smart.test'
        cli_namespace = 'task.smart_test'

    tests = {}

    @private
    async def set_test_data(self, disk, data):
        self.tests[disk] = data

    @private
    async def get_test_data(self, disk):
        return self.tests.get(disk)

    @private
    async def pop_test_data(self, disk):
        return self.tests.pop(disk, None)


class SMARTTestEventSource(EventSource):
    """
    Reports current S.M.A.R.T. test progress for the specified disk.
    """

    async def run(self):
        disk = self.arg

        while not self._cancel.is_set():
            data = await self.middleware.call('smart.test.get_test_data', disk)

            try:
                current_test = (await self.middleware.call(
                    'smart.test.results',
                    [['disk', '=', disk]],
                    {'get': True}
                ))['current_test']
            except MatchNotFound:
                current_test = None

            if current_test is None:
                await self.middleware.call('smart.test.pop_test_data', disk)
                self.send_event('ADDED', fields={'progress': None})
                return

            self.send_event('ADDED', fields={'progress': current_test['progress']})

            if data:
                # Check every percent
                interval = int((data['end_monotime'] - data['start_monotime']) / 100)

                if time.monotonic() < data['end_monotime']:
                    # but not more often than every ten seconds
                    interval = max(interval, 10)
                else:
                    # the test is taking longer than expected, do not poll more often than every minute
                    interval = max(interval, 60)
            else:
                # Test was started at an unknown time
                interval = 60

            await asyncio.sleep(interval)


def setup(middleware):
    middleware.register_event_source('smart.test.progress', SMARTTestEventSource)
