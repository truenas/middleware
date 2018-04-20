#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, POST

TESTFILE_NAME = "tftp-testfile.txt"
TESTFILE_PATH = "/tmp/"


def test_01_Creating_dataset_tank_tftproot():
    payload = {"name": "tftproot"}
    results = POST("/storage/volume/tank/datasets/", payload)
    assert results.status_code == 201, results.text


def test_02_Setting_permissions_for_TFTP_on_mnt_tank_tftproot():
    payload = {"mp_path": "/mnt/tank/tftproot",
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "nobody",
               "mp_group": "nobody"}
    results = PUT("/storage/permission/", payload)
    assert results.status_code == 201, results.text


def test_03_Configuring_TFTP_service():
    payload = {"tftp_directory": "/mnt/tank/tftproot",
               "tftp_username": "nobody",
               "tftp_newfiles": True}
    results = PUT("/services/tftp/", payload)
    assert results.status_code == 200, results.text


def test_04_Starting_TFTP_service():
    results = PUT("/services/services/tftp/", {"srv_enable": True})
    assert results.status_code == 200, results.text


def test_05_Checking_to_see_if_TFTP_service_is_enabled():
    results = GET("/services/services/tftp/")
    assert results.json()["srv_state"] == "RUNNING", results.text
