#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET
from auto_config import disk0


def test_01_boot_get_disks():
    results = GET('/boot/get_disks/')
    assert results.status_code == 200, results.text
    disks = results.json()
    assert isinstance(disks, list) is True, results.text
    assert disks[0] == disk0, results.text
