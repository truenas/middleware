#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import unittest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT


TestName = "create emails"


class create_email_test(unittest.TestCase):

    def test_01_Configuring_email_settings(self):
        payload = {"em_fromemail": "william.spam@ixsystems.com",
                   "em_outgoingserver": "mail.ixsystems.com",
                   "em_pass": "changeme",
                   "em_port": 25,
                   "em_security": "plain",
                   "em_smtp": "true",
                   "em_user": "william.spam@ixsystems.com"}
        assert PUT("/system/email/", payload) == 200
