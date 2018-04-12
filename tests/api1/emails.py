#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT


def test_01_Configuring_email_settings():
    payload = {"em_fromemail": "william.spam@ixsystems.com",
               "em_outgoingserver": "mail.ixsystems.com",
               "em_pass": "changeme",
               "em_port": 25,
               "em_security": "plain",
               "em_smtp": "true",
               "em_user": "william.spam@ixsystems.com"}
    results = PUT("/system/email/", payload)
    assert results.status_code == 200, results.text
