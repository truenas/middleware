#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT


def test_01_Enabling_UPS_Service():
    results = PUT("/services/services/ups/", {"srv_enable": True})
    assert results.status_code == 200, results.text


def test_02_Enabling_Remote_Monitor():
    results = PUT("/services/services/ups/", {"ups_rmonitor": True})
    assert results.status_code == 200, results.text


def test_03_Disabling_Remote_Monitor_option():
    results = PUT("/services/services/ups/", {"ups_rmonitor": False})
    assert results.status_code == 200, results.text


def test_04_Enabling_email_status_update_option():
    results = PUT("/services/services/ups/", {"ups_emailnotify": True})
    assert results.status_code == 200, results.text


def test_05_Disabling_email_status_update_option():
    results = PUT("/services/services/ups/", {"ups_emailnotify": False})
    assert results.status_code == 200, results.text


def test_06_running_UPS_in_Master_Mode():
    results = PUT("/services/services/ups/", {"ups_mode": "master"})
    assert results.status_code == 200, results.text


def test_07_Running_UPS_in_Slave_Mode():
    results = PUT("/services/services/ups/", {"ups_mode": "slave"})
    assert results.status_code == 200, results.text


def test_08_Setting_UPS_shutdown_mode_Battery():
    results = PUT("/services/services/ups/", {"ups_shutdown": "batt"})
    assert results.status_code == 200, results.text


def test_09_Setting_UPS_shutdown_mode_Low_Battery():
    results = PUT("/services/services/ups/", {"ups_shutdown": "lowbatt"})
    assert results.status_code == 200, results.text


def test_10_Disabling_UPS_Service():
    results = PUT("/services/services/ups/", {"srv_enable": False})
    assert results.status_code == 200, results.text


def test_11_Setting_Identifier():
    results = PUT("/services/services/ups/", {"ups_identifier": "ups"})
    assert results.status_code == 200, results.text
