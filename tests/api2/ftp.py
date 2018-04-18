#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API 2.0 of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, POST  # , RC_TEST
# from auto_config import ip


def test_01_Configuring_ftp():
    payload = {"clients": 10, "rootlogin": True}
    results = PUT("/ftp", payload)
    assert results.status_code == 200, results.text


def test_02_Look_at_ftp_cofiguration():
    results = GET("/ftp")
    assert results.json()["clients"] == 10, results.text
    assert results.json()["rootlogin"] == True, results.text


def test_03_enable_ftp_service_at_boot():
    payload = {"enable": True}
    results = PUT('/service/id/6', payload)
    assert results.status_code == 200, results.text


def test_04_look_ftp_service_at_boot():
    results = GET('/service')
    assert results.json()[3]["enable"] == True


def test_05_Starting_ftp_service():
    payload = {"service": "ftp", "service-control": {"onetime": True}}
    results = POST("/service/start", payload)
    assert results.status_code == 200, results.text


def test_06_Checking_to_see_if_FTP_service_is_enabled():
    results = GET('/service')
    assert results.json()[3]["state"] == "RUNNING"


# def test_04_Fetching_file_via_FTP():
#     cmd = "ftp -o /tmp/ftpfile ftp://testuser:test@" + ip + "/.cshrc"
#     RC_TEST(cmd) is True
