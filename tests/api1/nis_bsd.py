#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET
from config import *

# define variables
DATASET = "nis-bsd"
NIS_PATH = "/mnt/tank/" + DATASET
Reason = "NISSERVER and NISDOMAIN are missing in ixautomation.conf"

nis_test_cfg = pytest.mark.skipif(all(["NISSERVER" in locals(),
                                       "NISDOMAIN" in locals()
                                       ]) is False, reason=Reason)


@nis_test_cfg
def test_01_Setting_NIS_domain():
    results = PUT("/directoryservice/nis/", {"nis_domain": NISDOMAIN})
    assert results.status_code == 200, results.text


@nis_test_cfg
def test_02_Setting_NIS_server():
    results = PUT("/directoryservice/nis/", {"nis_servers": NISSERVER})
    assert results.status_code == 200, results.text


@nis_test_cfg
def test_03_Enabling_NIS_service():
    results = PUT("/directoryservice/nis/", {"nis_enable": True})
    assert results.status_code == 200, results.text


@nis_test_cfg
def test_04_Checking_if_NIS_service_is_enable():
    results = GET("/directoryservice/nis/")
    assert results.json()["nis_enable"] is True, results.text


@nis_test_cfg
def test_05_Creating_NIS_dataset():
    results = POST("/storage/volume/tank/datasets/", {"name": DATASET})
    assert results.status_code == 201, results.text


@nis_test_cfg
def test_06_Enabling_secure_mode():
    results = PUT("/directoryservice/nis/", {"nis_secure_mode": True})
    assert results.status_code == 200, results.text


@nis_test_cfg
def test_07_Checking_if_secure_mode_is_enable():
    results = GET("/directoryservice/nis/")
    assert results.json()["nis_secure_mode"] is True, results.text


@nis_test_cfg
def test_08_Disabling_secure_mode():
    results = PUT("/directoryservice/nis/", {"nis_secure_mode": False})
    assert results.status_code == 200, results.text


@nis_test_cfg
def test_09_Enabling_manycast():
    results = PUT("/directoryservice/nis/", {"nis_manycast": True})
    assert results.status_code == 200, results.text


@nis_test_cfg
def test_10_Checking_if_manycast_is_enable():
    results = GET("/directoryservice/nis/")
    assert results.json()["nis_manycast"] is True, results.text


@nis_test_cfg
def test_11_Disabling_manycast():
    results = PUT("/directoryservice/nis/", {"nis_manycast": False})
    assert results.status_code == 200, results.text


@nis_test_cfg
def test_12_Disabling_NIS_service():
    results = PUT("/directoryservice/nis/", {"nis_enable": False})
    assert results.status_code == 200, results.text
