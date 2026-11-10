import pprint

import pytest

from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call, client, mock, poll


def subscribe_job_events(c):
    events = []

    def callback(type, **message):
        events.append((type, message["fields"]))

    c.subscribe("core.get_jobs", callback, sync=True)
    return events


def job_wait(c, job_id):
    # `core.job_wait` returns only after the server has sent every event of the job it waits for.
    return c.call("core.job_wait", job_id, job=True)


def job_events(events, method):
    return [(type, fields) for type, fields in events if fields["method"] == method]


def job_progress(events, method):
    return [(type, fields["state"], fields["progress"]["percent"]) for type, fields in job_events(events, method)]


def test_successful_job_events():
    with mock("test.test1", """
        from middlewared.service import job

        @job()
        def mock(self, job, *args):
            return 42
    """):
        with client() as c:
            events = subscribe_job_events(c)

            assert job_wait(c, c.call("test.test1")) == 42

            assert job_progress(events, "test.test1") == [
                ("ADDED", "WAITING", 0),
                ("CHANGED", "RUNNING", 0),
                ("CHANGED", "SUCCESS", 100),
            ], pprint.pformat(events, indent=2)
            assert job_events(events, "test.test1")[-1][1]["result"] == 42


def test_failed_job_events():
    with mock("test.test1", """
        from middlewared.service import job

        @job()
        def mock(self, job, *args):
            raise ValueError("canary")
    """):
        with client() as c:
            events = subscribe_job_events(c)

            with pytest.raises(Exception, match="canary"):
                job_wait(c, c.call("test.test1"))

            assert job_progress(events, "test.test1") == [
                ("ADDED", "WAITING", 0),
                ("CHANGED", "RUNNING", 0),
                ("CHANGED", "FAILED", 0),
            ], pprint.pformat(events, indent=2)


def test_aborted_job_events():
    with mock("test.test1", """
        from middlewared.service import job

        @job(abortable=True)
        async def mock(self, job, *args):
            import asyncio
            await asyncio.sleep(60)
    """):
        with client() as c:
            events = subscribe_job_events(c)
            job_id = c.call("test.test1")
            poll(
                lambda: job_progress(events, "test.test1"),
                condition=lambda progress: ("CHANGED", "RUNNING", 0) in progress,
                timeout=10,
                interval=0.1,
                message="The job did not start",
            )

            c.call("core.job_abort", job_id)
            job_wait(c, job_id)

            assert job_progress(events, "test.test1") == [
                ("ADDED", "WAITING", 0),
                ("CHANGED", "RUNNING", 0),
                ("CHANGED", "ABORTED", 0),
            ], pprint.pformat(events, indent=2)


def test_wrapped_job_progress_events():
    with mock("test.test2", """
        from middlewared.service import job

        @job()
        def mock(self, job, *args):
            return 42
    """):
        with mock("test.test1", """
            from middlewared.service import job

            @job()
            async def mock(self, job, *args):
                return await job.wrap(await self.middleware.call("test.test2"))
        """):
            with client() as c:
                events = subscribe_job_events(c)

                assert job_wait(c, c.call("test.test1")) == 42

                assert job_progress(events, "test.test2") == [
                    ("ADDED", "WAITING", 0),
                    ("CHANGED", "RUNNING", 0),
                    ("CHANGED", "SUCCESS", 100),
                ], pprint.pformat(events, indent=2)
                assert job_progress(events, "test.test1") == [
                    ("ADDED", "WAITING", 0),
                    ("CHANGED", "RUNNING", 0),
                    ("CHANGED", "RUNNING", 100),
                    ("CHANGED", "SUCCESS", 100),
                ], pprint.pformat(events, indent=2)


def test_unprivileged_user_only_sees_its_own_jobs_events():
    with mock("test.test1", """
        from middlewared.service import job

        @job()
        def mock(self, job, *args):
            return 42
    """):
        with unprivileged_user_client(roles=["MOCK"]) as c:
            events = []

            def callback(type, **message):
                events.append((type, message))

            c.subscribe("core.get_jobs", callback, sync=True)

            call("test.test1", "secret", job=True)
            c.call("test.test1", "not secret", job=True)

            assert all(event[1]["fields"]["arguments"] == ["not secret"]
                       for event in events), pprint.pformat(events, indent=2)
