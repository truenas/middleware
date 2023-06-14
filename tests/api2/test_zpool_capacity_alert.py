import pytest
from pytest_dependency import depends

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call, mock, pool
from auto_config import dev_test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


def test__does_not_emit_alert(request):
    with mock("zfs.pool.query", return_value=[
        {
            "name": pool,
            "properties": {
                "capacity": {
                    "parsed": "50",
                }
            },
        }
    ]):
        assert call("alert.run_source", "ZpoolCapacity") == []


def test__emits_alert(request):
    with mock("zfs.pool.query", return_value=[
        {
            "name": pool,
            "properties": {
                "capacity": {
                    "parsed": "85",
                }
            },
        }
    ]):
        alerts = call("alert.run_source", "ZpoolCapacity")
        assert len(alerts) == 1
        assert alerts[0]["klass"] == "ZpoolCapacityWarning"
        assert alerts[0]["key"] == f'["{pool}"]'
        assert alerts[0]["args"] == {"volume": pool, "capacity": 85}


def test__does_not_flap_alert(request):
    with mock("zfs.pool.query", return_value=[
        {
            "name": pool,
            "properties": {
                "capacity": {
                    "parsed": "79",
                }
            },
        }
    ]):
        with pytest.raises(CallError) as e:
            call("alert.run_source", "ZpoolCapacity")

        assert e.value.errno == CallError.EALERTCHECKERUNAVAILABLE
