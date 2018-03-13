#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET_OUTPUT

TestName = "update alerts"
ALERT_MSG = "Testing system alerts with failure."


class update_alerts_test(unittest.TestCase):

    def test_01_Polling_API_endpoint_for_new_system_alert(self):
        assert GET_OUTPUT("/system/alert/", "message") == ALERT_MSG

    def test_02_Validating_API_alert_values(self):
        assert GET_OUTPUT("/system/alert/", "level") == "CRIT"
        assert GET_OUTPUT("/system/alert/", "dismissed") is False
