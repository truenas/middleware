#!/usr/bin/env python3

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

from functions import GET
from auto_config import ha


if ha:
    def test_01_test_failover_get_ips():
        results = GET('/failover/get_ips', controller_a=ha)
        assert results.status_code == 200, results.text
        rv = results.json()
        assert (isinstance(rv, list) and rv), rv
