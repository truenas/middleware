import subprocess
import time

from middlewared.schema import accepts, Int
from middlewared.service import private, Service, ValidationErrors
from middlewared.service_exception import CallError

MAX_PERMITTED_SLEW = 86400 * 30


class SystemService(Service):

    @private
    @accepts(Int('new_time', required=True))
    def set_time(self, ts):
        """
        This endpoint sets RTC to UTC and then sets the time to the specified
        value.
        """
        verr = ValidationErrors()
        if ts < 0:
            verr.add('system_set_time.new_time', 'timestamp must be positive value')

        if abs(ts - time.time()) > MAX_PERMITTED_SLEW:
            verr.add(
                'system_set_time.new_time',
                'new timestamp requires slewing clock more than maximum permitted value of 30 days'
            )

        verr.check()

        # stop NTP service before making clock changes
        self.middleware.call_sync('service.stop', 'ntpd')

        # Make sure RTC is set to UTC
        timedatectl = subprocess.run(['timedatectl', 'set-local-rtc', '0'], capture_output=True, check=False)
        if timedatectl.returncode:
            self.middleware.call_sync('service.start', 'ntpd')
            raise CallError(f'Failed to set RTC to UTC: {timedatectl.stderr.decode()}')

        # Set to our new timestamp
        timedatectl = subprocess.run(['timedatectl', 'set-time', f'@{int(ts)}'], capture_output=True, check=False)
        if timedatectl.returncode:
            self.middleware.call_sync('service.start', 'ntpd')
            raise CallError(f'Failed to set clock to ({ts}): {timedatectl.stderr.decode()}')

        self.middleware.call_sync('service.start', 'ntpd')
