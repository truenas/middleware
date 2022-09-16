import time
import pytest
from middlewared.test.integration.utils import call, mock
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason="Skipping for test development testing")


def test_cputemp():
    with mock("reporting.cpu_temperatures", return_value={0: 55, 1: 50}):
        for i in range(10):
            # collectd collects data every 10 seconds, but we might need to wait longer, as values might behave weird
            # when going from NaN to values for a few points (looks like an interpolation polynomial oscillation at the
            # edges of the interval)
            time.sleep(11)

            now = int(time.time())
            result = call("reporting.get_data", [{"name": "cputemp"}], {"start": now - 3600, "end": now})

            data = result[0]["data"]
            if data[-1] == [None, None]:
                data.pop()

            if data[-1] == [55, 50]:
                break
        else:
            assert False, result


def test_interface_stats():
    plugins = ("interfacepackets", "interfacebits", "interfaceerrors", "interfacedropped")
    for i in call("interface.query"):
        args = [{"name": j, "identifier": i} for j in plugins]
        opts = {"unit": "HOUR"}

        # need to make sure we can query each interface and the associated
        # plugins rrd file and ensure there is data being returned
        result = call("reporting.get_data", args, opts)
        assert result, result
