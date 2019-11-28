import asyncio
import threading
import time

import pytest

from middlewared.service import throttle


@pytest.mark.timeout(10)
def test__throttle():
    values = []
    errors = []

    @throttle(2, max_waiters=2)
    def f():
        return time.monotonic()

    def body():
        try:
            values.append(f())
        except Exception as e:
            errors.append(e)

    start = time.monotonic()
    t1 = threading.Thread(target=body)
    t1.start()
    t2 = threading.Thread(target=body)
    t2.start()
    t3 = threading.Thread(target=body)
    t3.start()

    t1.join()
    t2.join()
    t3.join()

    assert len(values) == 3
    assert len(errors) == 0

    values = sorted(values)
    assert values[0] - start < 1
    assert 1.99 <= values[1] - values[0] < 3
    assert 1.99 <= values[2] - values[1] < 3


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test__async_throttle():
    values = []
    errors = []

    @throttle(2, max_waiters=2)
    async def f():
        return time.monotonic()

    async def body():
        try:
            values.append(await f())
        except Exception as e:
            errors.append(e)

    start = time.monotonic()
    await asyncio.wait([asyncio.ensure_future(body()) for _ in range(3)])

    assert len(values) == 3
    assert len(errors) == 0

    values = sorted(values)
    assert values[0] - start < 1
    assert 1.99 <= values[1] - values[0] < 3
    assert 1.99 <= values[2] - values[1] < 3
