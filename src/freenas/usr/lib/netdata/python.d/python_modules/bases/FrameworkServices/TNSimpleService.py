import time

from bases.collection import safe_print
from bases.FrameworkServices.SimpleService import ND_INTERNAL_MONITORING_DISABLED, RUNTIME_CHART_UPDATE, SimpleService
from third_party.monotonic import monotonic


class TNService(SimpleService):
    """
    Override SimpleService to collect data immediately on startup instead of waiting
    for the first interval boundary.

    Original SimpleService behavior:
    - sleep_until_next() called BEFORE first update()
    - Charts appeared after ~100 seconds
    - First data collection delayed until next update_every boundary

    TNService behavior:
    - update() called immediately on startup
    - Charts appear within ~5 seconds
    - Data becomes queryable at next update_every boundary (typically ~5 minutes for
      update_every=300) due to netdata's timestamp alignment in rrdset_collection.c
    """

    def run(self):
        """
        Runs job in thread. Handles retries.
        Exits when job failed or timed out.
        :return: None
        """
        job = self._runtime_counters
        self.debug('started, update frequency: {freq}'.format(freq=job.update_every))

        job.start_mono = monotonic()
        job.start_real = time.time()

        while True:
            since = 0
            if job.prev_update:
                since = int((job.start_real - job.prev_update) * 1e6)

            try:
                updated = self.update(interval=since)
            except Exception as error:
                self.error('update() unhandled exception: {error}'.format(error=error))
                updated = False

            job.runs += 1

            if not updated:
                job.handle_retries()
            else:
                job.elapsed = int((monotonic() - job.start_mono) * 1e3)
                job.prev_update = job.start_real
                job.retries, job.penalty = 0, 0
                if not ND_INTERNAL_MONITORING_DISABLED:
                    safe_print(RUNTIME_CHART_UPDATE.format(job_name=self.name,
                                                           since_last=since,
                                                           elapsed=job.elapsed))
            self.debug('update => [{status}] (elapsed time: {elapsed}, failed retries in a row: {retries})'.format(
                status='OK' if updated else 'FAILED',
                elapsed=job.elapsed if updated else '-',
                retries=job.retries))

            job.sleep_until_next()
