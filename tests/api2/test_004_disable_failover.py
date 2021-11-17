#!/usr/bin/env python3

import os
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT
from auto_config import ha


if ha:
    def test_01_disable_failover():
        payload = {
            "disabled": True,
            "master": True,
        }
        results = PUT('/failover/', payload, controller_a=ha)
        assert results.status_code == 200, results.text
