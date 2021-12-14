#!/usr/bin/env python3

import os
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST
from auto_config import ha

if 'license_file' in os.environ:
    license_file = os.environ["license_file"]
else:
    license_file = '/root/license.txt'

# Only run the test below on HA
if ha:
    def test_01_send_license():
        with open(license_file, 'r') as f:
            results = POST('/system/license_update', str(f.read()), controller_a=ha)
            assert results.status_code == 200, results.text
