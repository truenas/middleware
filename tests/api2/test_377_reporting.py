import time
import pytest

# Middleware client need to be installed for the test belo or it will skip
try:
    from middlewared.test.integration.utils import *
except ImportError:
    Reason = 'middleware client library not installed'
    pytestmark = pytest.mark.skip(reason=Reason)

def test_cputemp():
    with mock("reporting.cpu_temperatures", return_value={0: 55, 1: 50}):
        for i in range(10):
            # collectd collects data every 10 seconds, but we might need to wait longer, as values might behave weird
            # when going from NaN to values for a few points (looks like an interpolation polynomial oscillation at the
            # edges of the interval)
            time.sleep(11)

            now = int(time.time())
            result = call("reporting.get_data", [{"name":"cputemp"}], {"start": now - 3600, "end": now})

            data = result[0]["data"]
            if data[-1] == [None, None]:
                data.pop()

            if data[-1] == [55, 50]:
                break
        else:
            assert False, result
