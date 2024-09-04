from time import sleep

import pytest
from pytest_dependency import depends

from auto_config import pool_name
from middlewared.test.integration.utils import call, ssh


ID_PATH = "/dev/disk/by-partuuid/"


def get_alert_by_id(alert_id):
    return next(filter(lambda alert: alert["id"] == alert_id, call("alert.list")), None)


@pytest.mark.dependency(name="degrade_pool")
def test_degrading_a_pool_to_create_an_alert(request):
    get_pool = call("pool.query", [["name", "=", pool_name]], {"get": True})
    gptid = get_pool["topology"]["data"][0]["path"].replace(ID_PATH, "")
    ssh(f"zinject -d {gptid} -A fault {pool_name}")
    request.config.cache.set("alert/gptid", gptid)


def test_verify_the_pool_is_degraded(request):
    depends(request, ["degrade_pool"], scope="session")
    gptid = request.config.cache.get("alert/gptid", "Not a valid id")
    status = call("zpool.status", {"name": pool_name})[pool_name][ID_PATH + gptid]["disk_status"]
    assert status == "DEGRADED"


@pytest.mark.timeout(120)
@pytest.mark.dependency(name="set_alert_id")
def test_wait_for_the_alert_and_get_the_id(request):
    depends(request, ["degrade_pool"], scope="session")
    call("alert.process_alerts")
    while True:
        for line in call("alert.list"):
            if (
                line["source"] == "VolumeStatus" and
                line["args"]["volume"] == pool_name and
                line["args"]["state"] == "DEGRADED"
            ):
                request.config.cache.set("alert/alert_id", line["id"])
                return
        sleep(1)


def test_verify_the_alert_is_dismissed(request):
    depends(request, ["degrade_pool", "set_alert_id"], scope="session")
    alert_id = request.config.cache.get("alert/alert_id", "Not a valid id")
    call("alert.dismiss", alert_id)
    alert = get_alert_by_id(alert_id)
    assert alert["dismissed"] is True, alert


def test_verify_the_alert_is_restored(request):
    depends(request, ["degrade_pool", "set_alert_id"], scope="session")
    alert_id = request.config.cache.get("alert/alert_id", "Not a valid id")
    call("alert.restore", alert_id)
    alert = get_alert_by_id(alert_id)
    assert alert["dismissed"] is False, alert


def test_clear_the_pool_degradation(request):
    depends(request, ["degrade_pool"], scope="session")
    ssh(f"zpool clear {pool_name}")


def test_verify_the_pool_is_not_degraded(request):
    depends(request, ["degrade_pool"], scope="session")
    gptid = request.config.cache.get("alert/gptid", "Not a valid id")
    status = call("zpool.status", {"name": pool_name})[pool_name][ID_PATH + gptid]["disk_status"]
    assert status != "DEGRADED"


@pytest.mark.timeout(120)
def test_wait_for_the_alert_to_disappear(request):
    depends(request, ["degrade_pool", "set_alert_id"], scope="session")
    alert_id = request.config.cache.get("alert/alert_id", "Not a valid id")
    while get_alert_by_id(alert_id) is not None: 
        sleep(1)
