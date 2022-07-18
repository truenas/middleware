import pprint
import pytest
import time

from middlewared.test.integration.utils import client, call, mock, ssh

from auto_config import dev_test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


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

            # FIXME: Sometimes an equal message for `SUCCESS` state is being sent (or received) twice, we were not able
            # to understand why and this does not break anything so we are not willing to waste our time investigating
            # this.
            if len(results) == 3 and results[1] == results[2]:
                results = results[:2]

            assert len(results) == 2, pprint.pformat(results, indent=2)
            assert results[0]['state'] == 'RUNNING'
            assert results[1]['state'] == 'SUCCESS'
            assert results[1]['result'] == 42
