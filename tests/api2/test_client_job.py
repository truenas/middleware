import pprint
import time

from middlewared.test.integration.utils import client, call, mock, ssh


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
