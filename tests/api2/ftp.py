#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API 2.0 of FreeNAS

import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, POST, dns_service_resolve
from auto_config import hostname
# from auto_config import ip


def test_01_Configuring_ftp():
    payload = {"clients": 10, "rootlogin": True}
    results = PUT("/ftp/", payload)
    assert results.status_code == 200, results.text


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
    payload = {"service": "ftp", "service-control": {"onetime": True}}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_06_Checking_to_see_if_FTP_service_is_enabled():
    results = GET('/service?service=ftp')
    assert results.json()[0]["state"] == "RUNNING"


@pytest.mark.skip(reason='mdnsadvertise.restart not into ftp service yet')
def test_07_verify_ftp_mdns_service_record():
    results = dns_service_resolve(hostname, 'local', '_ftp._tcp.')
    assert results['status'] is True, str(results['results'])
    assert results['results']['port'] == 21, str(results['results'])


# def test_04_Fetching_file_via_FTP():
#     cmd = "ftp -o /tmp/ftpfile ftp://testuser:test@" + ip + "/.cshrc"
#     RC_TEST(cmd) is True
