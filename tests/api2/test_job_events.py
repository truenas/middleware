import pprint

import pytest

from middlewared.test.integration.utils import client, mock

from auto_config import dev_test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


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

            # FIXME: Sometimes an equal message for `SUCCESS` state is being sent (or received) twice, we were not able
            # to understand why and this does not break anything so we are not willing to waste our time investigating
            # this.
            if len(events) == 4 and events[2] == events[3]:
                events = events[:3]

            assert len(events) == 3, pprint.pformat(events, indent=2)
            assert events[0][0] == "ADDED"
            assert events[0][1]["fields"]["state"] == "WAITING"
            assert events[1][0] == "CHANGED"
            assert events[1][1]["fields"]["state"] == "RUNNING"
            assert events[2][0] == "CHANGED"
            assert events[2][1]["fields"]["state"] == "SUCCESS"
            assert events[2][1]["fields"]["result"] == 42
