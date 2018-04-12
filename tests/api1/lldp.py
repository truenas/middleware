#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, GET_OUTPUT

LOCATION = "Maryville, TN"
COUNTRY = "US"
INTDESC = True


def test_01_Configuring_LLDP_service():
    payload = {"lldp_country": COUNTRY,
               "lldp_intdesc": INTDESC,
               "lldp_location": LOCATION}

    results = PUT("/services/lldp/", payload)
    assert results.status_code == 200, results.text


def test_02_Checking_that_API_reports_LLDP_service():
    results = GET("/services/lldp/")
    assert results.status_code == 200, results.text


def test_03_Checking_that_API_reports_LLDP_configuration_as_saved():
    results = GET_OUTPUT("/services/lldp/", "lldp_country")
    assert results == COUNTRY
    results = GET_OUTPUT("/services/lldp/", "lldp_intdesc")
    assert results == INTDESC
    results = GET_OUTPUT("/services/lldp/", "lldp_location")
    assert results == LOCATION


def test_04_Enable_LLDP_service():
    results = PUT("/services/services/lldp/", {"srv_enable": True})
    assert results.status_code == 200, results.text


def test_05_Checking_to_see_if_LLDP_service_is_running():
    results = GET_OUTPUT("/services/services/lldp/", "srv_state")
    assert results == "RUNNING"
