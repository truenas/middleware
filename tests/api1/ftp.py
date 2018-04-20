#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, RC_TEST
from auto_config import ip


# Create tests
def test_01_Configuring_ftp_service():
    payload = {"ftp_clients": 10, "ftp_rootlogin": "true"}
    results = PUT("/services/ftp/", payload)
    assert results.status_code == 200, results.text


def test_02_Starting_ftp_service():
    payload = {"srv_enable": "true"}
    results = PUT("/services/services/ftp/", payload)
    assert results.status_code == 200, results.text


def test_03_Checking_to_see_if_FTP_service_is_enabled():
    results = GET("/services/services/ftp/")
    assert results.json()["srv_state"] == "RUNNING", results.text


def test_04_Fetching_file_via_FTP():
    cmd = "ftp -o /tmp/ftpfile ftp://testuser:test@" + ip + "/.cshrc"
    RC_TEST(cmd) is True


# Update tests
def test_05_Stopping_ftp_service():
    results = PUT("/services/services/ftp/", {"srv_enable": False})
    assert results.status_code == 200, results.text


def test_06_Updating_ftp_service():
    results = PUT("/services/ftp/", {"ftp_clients": 20})
    assert results.status_code == 200, results.text


def test_07_Starting_ftp_service():
    results = PUT("/services/services/ftp/", {"srv_enable": True})
    assert results.status_code == 200, results.text


def test_08_Checking_to_see_if_FTP_service_is_enabled():
    results = GET("/services/services/ftp/")
    assert results.json()["srv_state"] == "RUNNING", results.text
