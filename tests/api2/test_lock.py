import time

import pytest

from middlewared.test.integration.utils import client, mock
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


@pytest.mark.flaky(reruns=5, reruns_delay=5)
def test_no_lock():
    with mock("test.test1", """
        from middlewared.service import lock

        async def mock(self, *args):
            import asyncio
            await asyncio.sleep(5)
    """):
        start = time.monotonic()

        with client() as c:
            c1 = c.call("test.test1", background=True)
            c2 = c.call("test.test1", background=True)
            c.wait(c1)
            c.wait(c2)

        assert time.monotonic() - start < 6


@pytest.mark.flaky(reruns=5, reruns_delay=5)
def test_async_lock():
    with mock("test.test1", """
        from middlewared.service import lock

        @lock("test")
        async def mock(self, *args):
            import asyncio
            await asyncio.sleep(5)
    """):
        start = time.monotonic()

        with client() as c:
            c1 = c.call("test.test1", background=True)
            c2 = c.call("test.test1", background=True)
            c.wait(c1)
            c.wait(c2)

        assert time.monotonic() - start >= 10


@pytest.mark.flaky(reruns=5, reruns_delay=5)
def test_threading_lock():
    with mock("test.test1", """
        from middlewared.service import lock

        @lock("test")
        def mock(self, *args):
            import time
            time.sleep(5)
    """):
        start = time.monotonic()

        with client() as c:
            c1 = c.call("test.test1", background=True)
            c2 = c.call("test.test1", background=True)
            c.wait(c1)
            c.wait(c2)

        assert time.monotonic() - start >= 10
