#!/usr/bin/env python3
from datetime import datetime
import os
import sys
import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, PUT, wait_on_job
from auto_config import dev_test
from pytest_dependency import depends
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


def test_00_bootstrap(request):
    depends(request, ["pool_04"], scope="session")

    result = POST("/pool/dataset/", {"name": "tank/snapshottask-retention-test"})
    assert result.status_code == 200, result.text
    result = POST("/pool/dataset/", {"name": "tank/snapshottask-retention-test-2"})
    assert result.status_code == 200, result.text


def test_change_retention(request):
    depends(request, ["pool_04"], scope="session")

    result = POST("/pool/snapshottask/", {
        "dataset": "tank/snapshottask-retention-test",
        "recursive": True,
        "exclude": [],
        "lifetime_value": 1,
        "lifetime_unit": "WEEK",
        "naming_schema": "auto-%Y-%m-%d-%H-%M-1y",
        "schedule": {
            "minute": "*",
        },
    })
    assert result.status_code == 200, result.text
    task_id = result.json()["id"]

    result = POST("/zfs/snapshot/", {
        "dataset": "tank/snapshottask-retention-test",
        "name": "auto-2021-04-12-06-30-1y",
    })
    assert result.status_code == 200, result.text

    result = GET("/zfs/snapshot/?id=tank/snapshottask-retention-test@auto-2021-04-12-06-30-1y")
    assert result.status_code == 200, result.text
    assert result.json()[0]["retention"] == {
        "datetime": {
            "$date": (datetime(2021, 4, 19, 6, 30) - datetime(1970, 1, 1)).total_seconds() * 1000,
        },
        "source": "periodic_snapshot_task",
        "periodic_snapshot_task_id": task_id,
    }

    result = POST(f"/pool/snapshottask/id/{task_id}/update_will_change_retention_for/", {
        "naming_schema": "auto-%Y-%m-%d-%H-%M-365d",
    })
    assert result.status_code == 200, result.text
    assert result.json() == {
        "tank/snapshottask-retention-test": ["auto-2021-04-12-06-30-1y"],
    }

    result = PUT(f"/pool/snapshottask/id/{task_id}/", {
        "naming_schema": "auto-%Y-%m-%d-%H-%M-365d",
        "fixate_removal_date": True,
    })
    assert result.status_code == 200, result.text

    results = GET('/core/get_jobs/?method=pool.snapshottask.fixate_removal_date')
    job_status = wait_on_job(results.json()[-1]['id'], 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    result = GET("/zfs/snapshot/?id=tank/snapshottask-retention-test@auto-2021-04-12-06-30-1y")
    assert result.status_code == 200, result.text
    assert (
        [v for k, v in result.json()[0]["properties"].items() if k.startswith("org.truenas:destroy_at_")][0]["value"]
        == "2021-04-19T06:30:00"
    )
    assert result.json()[0]["retention"] == {
        "datetime": {
            "$date": (datetime(2021, 4, 19, 6, 30) - datetime(1970, 1, 1)).total_seconds() * 1000,
        },
        "source": "property",
    }


def test_delete_retention(request):
    depends(request, ["pool_04"], scope="session")

    result = POST("/pool/snapshottask/", {
        "dataset": "tank/snapshottask-retention-test-2",
        "recursive": True,
        "exclude": [],
        "lifetime_value": 1,
        "lifetime_unit": "WEEK",
        "naming_schema": "auto-%Y-%m-%d-%H-%M-1y",
        "schedule": {
            "minute": "*",
        },
    })
    assert result.status_code == 200, result.text
    task_id = result.json()["id"]

    result = POST("/zfs/snapshot/", {
        "dataset": "tank/snapshottask-retention-test-2",
        "name": "auto-2021-04-12-06-30-1y",
    })
    assert result.status_code == 200, result.text

    result = POST(f"/pool/snapshottask/id/{task_id}/delete_will_change_retention_for/")
    assert result.status_code == 200, result.text
    assert result.json() == {
        "tank/snapshottask-retention-test-2": ["auto-2021-04-12-06-30-1y"],
    }

    result = DELETE(f"/pool/snapshottask/id/{task_id}/", {
        "fixate_removal_date": True,
    })
    assert result.status_code == 200, result.text

    results = GET('/core/get_jobs/?method=pool.snapshottask.fixate_removal_date')
    job_status = wait_on_job(results.json()[-1]['id'], 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    result = GET("/zfs/snapshot/?id=tank/snapshottask-retention-test-2@auto-2021-04-12-06-30-1y")
    assert result.status_code == 200, result.text
    assert (
        [v for k, v in result.json()[0]["properties"].items() if k.startswith("org.truenas:destroy_at_")][0]["value"]
        == "2021-04-19T06:30:00"
    )
    assert result.json()[0]["retention"] == {
        "datetime": {
            "$date": (datetime(2021, 4, 19, 6, 30) - datetime(1970, 1, 1)).total_seconds() * 1000,
        },
        "source": "property",
    }
