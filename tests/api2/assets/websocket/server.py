from time import sleep

from middlewared.test.integration.utils.client import client
from functions import ping_host


def reboot(ip, service_name=None):
    """Reboot the TrueNAS at the specified IP.
    Return when it has rebooted."""
    with client(host_ip=ip) as c:
        # we call this method to "reboot" the system
        # because it causes the system to go offline
        # immediately (kernel panic). We don't care
        # about clean shutdowns here, we're more
        # interested in the box rebooting as quickly
        # as possible.
        c.call('failover.become_passive')

    # Wait for server to reappear
    ping_count, reappear_time = 1, 120
    reappeared = ping_host(ip, ping_count, reappear_time)
    assert reappeared, f'TrueNAS at IP: {ip!r} did not come back online after {reappear_time!r} seconds'

    # TrueNAS network comes back before websocket
    # server is fully operational so account for this
    api_ready_time = 30
    for i in range(api_ready_time):
        try:
            with client(host_ip=ip) as c:
                if c.call('system.ready'):
                    break
        except Exception:
            pass
        else:
            sleep(1)
    else:
        assert False, f'TrueNAS at ip: {ip!r} failed to respond after {reappear_time + api_ready_time!r} seconds'

    if service_name:
        total_wait = 60
        for i in range(total_wait):
            try:
                with client(host_ip=ip) as c:
                    rv = c.call('service.query', [['service', '=', service_name]], {'get': True})
                    if rv['state'] == 'RUNNING':
                        break
            except Exception:
                pass
            else:
                sleep(1)
        else:
            assert False, f'Service: {service_name!r} on IP: {ip!r} not running following reboot'
