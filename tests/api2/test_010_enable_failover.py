#!/usr/bin/env python3

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT
from auto_config import ha

# Exclude for non-HA
if ha:
    def test_01_enable_failover():
        payload = {
            "disabled": False,
            "master": True,
        }
        results = PUT('/failover/', payload)
        assert results.status_code == 200, results.text
