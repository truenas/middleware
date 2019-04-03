#!/usr/bin/env python3.6

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, DELETE


@pytest.mark.skip("Need to be fix")
def test_01_create_scrub_for_same_pool():
    result = POST("/pool/scrub/", {
        "pool": 1,
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


def test_02_update_scrub():
    result = PUT("/pool/scrub/id/1/", {
        "pool": 1,
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


def test_03_delete_scrub():
    result = DELETE("/pool/scrub/id/1/")
    assert result.status_code == 200, result.text


def test_04_create_scrub():
    result = POST("/pool/scrub/", {
        "pool": 1,
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
