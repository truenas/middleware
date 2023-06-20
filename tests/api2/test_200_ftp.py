#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API 2.0 of FreeNAS

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, POST, SSH_TEST
from auto_config import dev_test, user, password, ip
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


def test_01_Configuring_ftp():
    payload = {"clients": 10, "rootlogin": True}
    results = PUT("/ftp/", payload)
    assert results.status_code == 200, results.text
    # Confirm we block no_cert_request: NAS-122492
    payload = {"tls_opt_no_cert_request": True}
    results = PUT("/ftp/", payload)
    assert results.status_code != 200, results.text


def test_02_Look_at_ftp_cofiguration():
    results = GET("/ftp/")
    assert results.json()["clients"] == 10, results.text
    assert results.json()["rootlogin"] is True, results.text


def test_03_enable_ftp_service_at_boot():
    payload = {"enable": True}
    results = PUT('/service/id/ftp/', payload)
    assert results.status_code == 200, results.text


def test_04_look_ftp_service_at_boot():
    results = GET('/service?service=ftp')
    assert results.json()[0]["enable"] is True


def test_05_Starting_ftp_service():
    payload = {"service": "ftp"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    # Confirm excluded settings: NAS-122492
    results = SSH_TEST("grep MultilineRFC2228: /etc/local/proftpd.conf", user, password, ip)
    assert results['result'] is False


def test_06_Checking_to_see_if_FTP_service_is_enabled():
    results = GET('/service?service=ftp')
    assert results.json()[0]["state"] == "RUNNING"
