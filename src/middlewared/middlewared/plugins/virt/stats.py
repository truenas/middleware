import time

from middlewared.event import EventSource
from middlewared.schema import Dict, Str
from middlewared.plugins.reporting.realtime_reporting.cgroup import get_cgroup_stats


class VirtInstacesMetricsEventSource(EventSource):

    ACCEPTS = Dict(
        Str('id'),
    )

    def run_sync(self):

        instance_id = self.arg['id']

        while not self._cancel_sync.is_set():

            netdata_metrics = None
            # TODO: code duplication with reporting.realtime
            # this gathers the most recent metric recorded via netdata (for all charts)
            retries = 2
            while retries > 0:
                try:
                    netdata_metrics = self.middleware.call_sync('netdata.get_all_metrics')
                except Exception:
                    retries -= 1
                    if retries <= 0:
                        raise

                    time.sleep(0.5)
                else:
                    break

            data = {}
            if not bool(netdata_metrics):
                data['error'] = True
                data['errname'] = 'FAILED_TO_CONNECT'
            else:
                data.update(get_cgroup_stats(netdata_metrics, [instance_id])[instance_id])
                data['error'] = False
                data['errname'] = None

            self.send_event('ADDED', fields=data)

            time.sleep(1)


async def setup(middleware):
    middleware.register_event_source(
        'virt.instance.metrics', VirtInstacesMetricsEventSource, roles=['VIRT_INSTANCE_READ']
    )
