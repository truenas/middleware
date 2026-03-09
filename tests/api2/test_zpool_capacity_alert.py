import pytest
from pytest_dependency import depends
from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call, mock, pool


MOCK_METHOD = "zpool.query_impl"


def _mock_pool(capacity):
    return {
        "name": pool,
        "guid": 0,
        "status": "ONLINE",
        "healthy": True,
        "warning": False,
        "status_code": "OK",
        "status_detail": None,
        "properties": {
            "capacity": {
                "value": capacity,
                "raw": f"{capacity}%",
                "source": "NONE",
            }
        },
        "topology": None,
        "scan": None,
        "expand": None,
        "features": None,
    }


def test__does_not_emit_alert(request):
    with mock(MOCK_METHOD, return_value=[_mock_pool(50)]):
        assert call("alert.run_source", "ZpoolCapacity") == []


def test__emits_alert(request):
    with mock(MOCK_METHOD, return_value=[_mock_pool(85)]):
        alerts = call("alert.run_source", "ZpoolCapacity")
        assert len(alerts) == 1
        assert alerts[0]["klass"] == "ZpoolCapacityNotice"
        assert alerts[0]["key"] == f'["{pool}"]'
        assert alerts[0]["args"] == {"volume": pool, "capacity": 85}


def test__does_not_flap_alert(request):
    with mock(MOCK_METHOD, return_value=[_mock_pool(84)]):
        with pytest.raises(CallError) as e:
            call("alert.run_source", "ZpoolCapacity")

        assert e.value.errno == CallError.EALERTCHECKERUNAVAILABLE
