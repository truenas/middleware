#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import SSH_TEST

alert_msg = "Testing system alerts with failure."
alert_status = "FAIL"
alert_file = "/tmp/self-test-alert"
TestName = "create a"


class create_alerts_test(unittest.TestCase):

    def test_01_Create_an_alert_on_the_remote_system(self):
        cmd = 'echo "[%s] %s" >> %s' % (alert_status, alert_msg, alert_file)
        assert SSH_TEST(cmd) is True
