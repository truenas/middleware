#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET_OUTPUT
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
    assert PUT("/directoryservice/nis/", {"nis_domain": NISDOMAIN}) == 200


@nis_test_cfg
def test_02_Setting_NIS_server():
    assert PUT("/directoryservice/nis/", {"nis_servers": NISSERVER}) == 200


@nis_test_cfg
def test_03_Enabling_NIS_service():
    assert PUT("/directoryservice/nis/", {"nis_enable": True}) == 200


@nis_test_cfg
def test_04_Checking_if_NIS_service_is_enable():
    assert GET_OUTPUT("/directoryservice/nis/", "nis_enable") is True


@nis_test_cfg
def test_05_Creating_NIS_dataset():
    assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201


@nis_test_cfg
def test_06_Enabling_secure_mode():
    assert PUT("/directoryservice/nis/", {"nis_secure_mode": True}) == 200


@nis_test_cfg
def test_07_Checking_if_secure_mode_is_enable():
    assert GET_OUTPUT("/directoryservice/nis/", "nis_secure_mode") is True


@nis_test_cfg
def test_08_Disabling_secure_mode():
    assert PUT("/directoryservice/nis/", {"nis_secure_mode": False}) == 200


@nis_test_cfg
def test_09_Enabling_manycast():
    assert PUT("/directoryservice/nis/", {"nis_manycast": True}) == 200


@nis_test_cfg
def test_10_Checking_if_manycast_is_enable():
    assert GET_OUTPUT("/directoryservice/nis/", "nis_manycast") is True


@nis_test_cfg
def test_11_Disabling_manycast():
    assert PUT("/directoryservice/nis/", {"nis_manycast": False}) == 200


@nis_test_cfg
def test_12_Disabling_NIS_service():
    assert PUT("/directoryservice/nis/", {"nis_enable": False}) == 200
