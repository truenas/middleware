import pprint

from middlewared.test.integration.utils import client, mock


def test_successful_job_events():
    with mock("test.test1", """    
        from middlewared.service import job

        @job()
        def mock(self, job, *args):
            return 42
    """):
        with client() as c:
            events = []

            def callback(type, **message):
                events.append((type, message))

            c.subscribe("core.get_jobs", callback, sync=True)
            c.call("test.test1", job=True)

            assert len(events) == 3, pprint.pformat(events, indent=2)
            assert events[0][0] == "ADDED"
            assert events[0][1]["fields"]["state"] == "WAITING"
            assert events[1][0] == "CHANGED"
            assert events[1][1]["fields"]["state"] == "RUNNING"
            assert events[2][0] == "CHANGED"
            assert events[2][1]["fields"]["state"] == "SUCCESS"
            assert events[2][1]["fields"]["result"] == 42
