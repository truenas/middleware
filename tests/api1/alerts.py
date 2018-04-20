#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import SSH_TEST
from auto_config import user, password, ip

alert_msg = "Testing system alerts with failure."
alert_status = "FAIL"
alert_file = "/tmp/self-test-alert"


# Create tests
def test_01_Create_an_alert_on_the_remote_system():
    cmd = 'echo "[%s] %s" > %s' % (alert_status, alert_msg, alert_file)
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


# Update tests
# def test_03_Polling_API_endpoint_for_new_system_alert():
#     assert GET_OUTPUT("/system/alert/", "message") == alert_msg


# def test_04_Validating_API_alert_values():
#     assert GET_OUTPUT("/system/alert/", "level") == "CRIT"
#     assert GET_OUTPUT("/system/alert/", "dismissed") is False
