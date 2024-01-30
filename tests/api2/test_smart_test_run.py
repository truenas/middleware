import contextlib
import re
import time

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call, client, mock
pytestmark = pytest.mark.disk


@pytest.fixture(scope="function")
def short_test():
    disk = call("disk.query")[0]
    with mock("smart.test.disk_choices", return_value={disk["identifier"]: disk}):
        with mock("disk.smartctl", return_value="Self Test has begun"):
            with mock("smart.test.results", """\
                    i = 0
                    async def mock(self, *args):
                        global i
                        if i > 100:
                            return {"current_test": None}
                        else:
                            result = {"current_test": {"progress": i}}
                            i += 30
                            return result 
            """):
                result = call("smart.test.manual_test", [{"identifier": disk["identifier"], "type": "SHORT"}])
                yield result[0]


def test_smart_test_job_progress(short_test):
    progresses = set()
    for i in range(30):
        job = call("core.get_jobs", [["id", "=", short_test["job"]]], {"get": True})
        if job["state"] == "RUNNING":
            progresses.add(job["progress"]["percent"])
            time.sleep(5)
        elif job["state"] == "SUCCESS":
            break
        else:
            assert False, job
    else:
        assert False

    assert progresses == {0, 30, 60, 90}


def test_smart_test_event_source(short_test):
    progresses = set()

    def callback(event_type, **kwargs):
        progresses.add(kwargs['fields']['progress'])

    with client() as c:
        c.subscribe(f"smart.test.progress:{short_test['disk']}", callback, sync=True)

        for i in range(30):
            if None in progresses:
                assert progresses - {0} == {30, 60, 90, None}
                break
            else:
                time.sleep(5)
        else:
            assert False
