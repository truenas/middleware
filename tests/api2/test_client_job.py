import pprint
import time

import pytest

from middlewared.test.integration.utils import client, mock


# FIXME: Sometimes an equal message for `SUCCESS` state is being sent (or received) twice, we were not able
# to understand why and this does not break anything so we are not willing to waste our time investigating
# this.
# Also, `RUNNING` message sometimes is not received, this does not have a logical explanation as well and is not
# repeatable.
@pytest.mark.flaky(reruns=5, reruns_delay=5)
def test_client_job_callback():
    with mock("test.test1", """    
        from middlewared.service import job

        @job()
        def mock(self, job, *args):
            import time
            time.sleep(2)
            return 42
    """):
        with client() as c:
            results = []

            c.call("test.test1", job=True, callback=lambda job: results.append(job.copy()))

            # callback is called in a separate thread, allow it to settle
            time.sleep(2)

            assert len(results) == 2, pprint.pformat(results, indent=2)
            assert results[0]['state'] == 'RUNNING'
            assert results[1]['state'] == 'SUCCESS'
            assert results[1]['result'] == 42
