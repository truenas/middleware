#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET
from auto_config import disk0


def test_01_get_boot_disks():
    results = GET('/boot/get_disks/')
    assert results.status_code == 200, results.text
    disks = results.json()
    assert isinstance(disks, list) is True, results.text
    assert disks[0] == disk0, results.text


def test_02_get_boot_state():
    results = GET('/boot/get_state/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    global boot_state
    boot_state = results.json()


def test_03_get_boot_scrub():
    results = GET('/boot/scrub/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int) is True, results.text
