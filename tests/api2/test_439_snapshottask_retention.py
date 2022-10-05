#!/usr/bin/env python3
from datetime import datetime
import os
import sys
import time

import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import assert_creates_job, call

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, PUT, wait_on_job
from auto_config import dev_test
from pytest_dependency import depends
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


def test_change_retention(request):
    depends(request, ["pool_04"], scope="session")

    with dataset("snapshottask-retention-test") as ds:
        call("zettarepl.load_removal_dates")

        result = POST("/pool/snapshottask/", {
            "dataset": ds,
            "recursive": True,
            "exclude": [],
            "lifetime_value": 50,
            "lifetime_unit": "YEAR",
            "naming_schema": "auto-%Y-%m-%d-%H-%M-1y",
            "schedule": {
                "minute": "*",
            },
        })
        assert result.status_code == 200, result.text
        task_id = result.json()["id"]
    
        result = POST("/zfs/snapshot/", {
            "dataset": ds,
            "name": "auto-2021-04-12-06-30-1y",
        })
        assert result.status_code == 200, result.text
    
        result = GET(f"/zfs/snapshot/?id={ds}@auto-2021-04-12-06-30-1y&extra.retention=true")
        assert result.status_code == 200, result.text
        assert result.json()[0]["retention"] == {
            "datetime": {
                "$date": (datetime(2071, 3, 31, 6, 30) - datetime(1970, 1, 1)).total_seconds() * 1000,
            },
            "source": "periodic_snapshot_task",
            "periodic_snapshot_task_id": task_id,
        }
    
        result = POST(f"/pool/snapshottask/id/{task_id}/update_will_change_retention_for/", {
            "naming_schema": "auto-%Y-%m-%d-%H-%M-365d",
        })
        assert result.status_code == 200, result.text
        assert result.json() == {
            ds: ["auto-2021-04-12-06-30-1y"],
        }

        with assert_creates_job("pool.snapshottask.fixate_removal_date") as job:
            result = PUT(f"/pool/snapshottask/id/{task_id}/", {
                "naming_schema": "auto-%Y-%m-%d-%H-%M-365d",
                "fixate_removal_date": True,
            })
            assert result.status_code == 200, result.text
    
        job_status = wait_on_job(job.id, 180)
        assert job_status["state"] == "SUCCESS", str(job_status["results"])
    
        result = GET(f"/zfs/snapshot/?id={ds}@auto-2021-04-12-06-30-1y&extra.retention=true")
        assert result.status_code == 200, result.text
        assert result.json()
        properties = [v for k, v in result.json()[0]["properties"].items() if k.startswith("org.truenas:destroy_at_")]
        assert properties, result.json()[0]["properties"]
        assert properties[0]["value"] == "2071-03-31T06:30:00"
        assert result.json()[0]["retention"] == {
            "datetime": {
                "$date": (datetime(2071, 3, 31, 6, 30) - datetime(1970, 1, 1)).total_seconds() * 1000,
            },
            "source": "property",
        }


def test_delete_retention(request):
    depends(request, ["pool_04"], scope="session")

    with dataset("snapshottask-retention-test-2") as ds:
        call("zettarepl.load_removal_dates")

        result = POST("/pool/snapshottask/", {
            "dataset": ds,
            "recursive": True,
            "exclude": [],
            "lifetime_value": 50,
            "lifetime_unit": "YEAR",
            "naming_schema": "auto-%Y-%m-%d-%H-%M-1y",
            "schedule": {
                "minute": "*",
            },
        })
        assert result.status_code == 200, result.text
        task_id = result.json()["id"]
    
        result = POST("/zfs/snapshot/", {
            "dataset": ds,
            "name": "auto-2021-04-12-06-30-1y",
        })
        assert result.status_code == 200, result.text
    
        result = POST(f"/pool/snapshottask/id/{task_id}/delete_will_change_retention_for/")
        assert result.status_code == 200, result.text
        assert result.json() == {
            ds: ["auto-2021-04-12-06-30-1y"],
        }

        with assert_creates_job("pool.snapshottask.fixate_removal_date") as job:
            result = DELETE(f"/pool/snapshottask/id/{task_id}/", {
                "fixate_removal_date": True,
            })
            assert result.status_code == 200, result.text

        job_status = wait_on_job(job.id, 180)
        assert job_status["state"] == "SUCCESS", str(job_status["results"])
    
        result = GET(f"/zfs/snapshot/?id={ds}@auto-2021-04-12-06-30-1y&extra.retention=true")
        assert result.status_code == 200, result.text
        assert result.json()
        properties = [v for k, v in result.json()[0]["properties"].items() if k.startswith("org.truenas:destroy_at_")]
        assert properties, result.json()[0]["properties"]
        assert properties[0]["value"] == "2071-03-31T06:30:00"
        assert result.json()[0]["retention"] == {
            "datetime": {
                "$date": (datetime(2071, 3, 31, 6, 30) - datetime(1970, 1, 1)).total_seconds() * 1000,
            },
            "source": "property",
        }
