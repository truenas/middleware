#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT, RC_TEST
from auto_config import ip


def test_01_Configuring_ftp_service():
    payload = {"ftp_clients": 10, "ftp_rootlogin": "true"}
    assert PUT("/services/ftp/", payload) == 200


def test_02_Starting_ftp_service():
    payload = {"srv_enable": "true"}
    assert PUT("/services/services/ftp/", payload) == 200


def test_03_Checking_to_see_if_FTP_service_is_enabled():
    assert GET_OUTPUT("/services/services/ftp/", "srv_state") == "RUNNING"


def test_04_Fetching_file_via_FTP():
    cmd = "ftp -o /tmp/ftpfile ftp://testuser:test@" + ip + "/.cshrc"
    RC_TEST(cmd) is True
