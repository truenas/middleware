#!/usr/bin/env python3

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT
from auto_config import ha


# Only read and run the test on HA
if ha:
    def test_01_disable_failover():
        payload = {
            "disabled": True,
            "master": True,
        }
        results = PUT('/failover/', payload, controller_a=ha)
        assert results.status_code == 200, results.text
