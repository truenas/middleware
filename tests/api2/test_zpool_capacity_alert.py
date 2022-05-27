import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call, mock


def test__does_not_emit_alert():
    with mock("zfs.pool.query", return_value=[
        {
            "name": "tank",
            "properties": {
                "capacity": {
                    "parsed": "50",
                }
            },
        }
    ]):
        assert call("alert.run_source", "ZpoolCapacity") == []


def test__emits_alert():
    with mock("zfs.pool.query", return_value=[
        {
            "name": "tank",
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
        assert alerts[0]["key"] == '["tank"]'
        assert alerts[0]["args"] == {"volume": "tank", "capacity": 85}


def test__does_not_flap_alert():
    with mock("zfs.pool.query", return_value=[
        {
            "name": "tank",
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
