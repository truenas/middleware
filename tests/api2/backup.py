#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE

DATASET = "tank/backup"
urlDataset = "tank%2Fbackup"
BACKUP_PATH = "/mnt/" + DATASET


def test_01_check_backup():
    results = GET("/backup/")
    assert results.status_code == 200, results.text


def test_02_creating_dataset_backup():
    payload = {"name": DATASET}
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.skip(reason="No ready yet")
def test_03_creating_backup_backup():
    payload = {"description": "Test backup",
               "direction": "PULL",
               "transfer_mode": "COPY",
               "path": "/mnt/tank/backup",
               "credential": 0,
               "minute": "1",
               "hour": "0",
               "daymonth": "0",
               "dayweek": "0",
               "month": "0",
               "enabled": True}
    results = POST("/backup/", payload)
    assert results.status_code == 200, results.text


# Check destroying a SMB dataset
def test_02_destroying_backup_dataset():
    results = DELETE(f"/pool/dataset/id/{urlDataset}/")
    assert results.status_code == 200, results.text
