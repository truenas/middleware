import pprint
import time

from middlewared.test.integration.utils import client, mock


def test_client_job_callback():
    with mock("test.test1", """
        from middlewared.service import job

        @job()
        def mock(self, job, *args):
            import time
            time.sleep(1)
            job.set_progress(50)
            time.sleep(1)
            return 42
    """):
        with client() as c:
            results = []

            c.call("test.test1", job=True, callback=lambda job: results.append(job.copy()))

            # callback is called in a separate thread, allow it to settle
            time.sleep(2)

            # The client attaches `callback` only after the first job event arrives, so thread timing decides
            # whether it also sees the WAITING and the initial RUNNING event.
            states = [result["state"] for result in results]
            assert states.count("SUCCESS") == 1, pprint.pformat(results, indent=2)
            assert results[-2]["state"] == "RUNNING"
            assert results[-2]["progress"]["percent"] == 50
            assert results[-1]["state"] == "SUCCESS"
            assert results[-1]["result"] == 42
