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
    assert PUT("/services/lldp/", payload) == 200


def test_02_Checking_that_API_reports_LLDP_service():
    assert GET("/services/lldp/") == 200


def test_03_Checking_that_API_reports_LLDP_configuration_as_saved():
    assert GET_OUTPUT("/services/lldp/", "lldp_country") == COUNTRY
    assert GET_OUTPUT("/services/lldp/", "lldp_intdesc") == INTDESC
    assert GET_OUTPUT("/services/lldp/", "lldp_location") == LOCATION


def test_04_Enable_LLDP_service():
    assert PUT("/services/services/lldp/", {"srv_enable": True}) == 200


def test_05_Checking_to_see_if_LLDP_service_is_running():
    assert GET_OUTPUT("/services/services/lldp/", "srv_state") == "RUNNING"
