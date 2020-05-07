#!/usr/bin/env python3

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, PUT, POST, DELETE
from auto_config import pool_name

pool_id = GET(f"/pool/?name={pool_name}").json()[0]["id"]


def test_01_create_scrub_for_same_pool():
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


def test_02_get_pool_name_scrub_id():
    global scrub_id
    result = GET(f"/pool/scrub/?pool_name={pool_name}")
    assert result.status_code == 200, result.text
    scrub_id = result.json()[0]['id']


def test_03_update_scrub():
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


def test_04_delete_scrub():
    result = DELETE(f"/pool/scrub/id/{scrub_id}/")
    assert result.status_code == 200, result.text


def test_05_create_scrub():
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
