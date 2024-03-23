#!/usr/bin/env python3

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, PUT, POST, DELETE
from auto_config import pool_name

pytestmark = pytest.mark.zfs


def test_01_create_scrub_for_same_pool(request):
    global pool_id
    pool_id = GET(f"/pool/?name={pool_name}").json()[0]["id"]
    result = POST("/pool/scrub/", {
        "pool": pool_id,
        "threshold": 1,
        "description": "",
        "schedule": {
            "minute": "00",
            "hour": "00",
            "dom": "1",
            "month": "1",
            "dow": "1",
        },
        "enabled": True,
    })
    assert result.status_code == 422, result.text
    text = "A scrub with this pool already exists"
    assert result.json()["pool_scrub_create.pool"][0]["message"] == text, result.text


def test_02_get_pool_name_scrub_id(request):
    global scrub_id
    result = GET(f"/pool/scrub/?pool_name={pool_name}")
    assert result.status_code == 200, result.text
    scrub_id = result.json()[0]['id']


def test_03_update_scrub(request):
    result = PUT(f"/pool/scrub/id/{scrub_id}/", {
        "pool": pool_id,
        "threshold": 2,
        "description": "",
        "schedule": {
            "minute": "00",
            "hour": "00",
            "dom": "1",
            "month": "1",
            "dow": "1",
        },
        "enabled": True,
    })
    assert result.status_code == 200, result.text


def test_04_delete_scrub(request):
    result = DELETE(f"/pool/scrub/id/{scrub_id}/")
    assert result.status_code == 200, result.text


def test_05_create_scrub(request):
    result = POST("/pool/scrub/", {
        "pool": pool_id,
        "threshold": 1,
        "description": "",
        "schedule": {
            "minute": "00",
            "hour": "00",
            "dom": "1",
            "month": "1",
            "dow": "1",
        },
        "enabled": True,
    })
    assert result.status_code == 200, result.text
