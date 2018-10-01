#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST


def test_01_update_get_trains():
    results = GET('/update/get_trains/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True


def test_02_update_check_available():
    results = POST('/update/check_available/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True


def test_03_update_get_pending():
    results = POST('/update/get_pending/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True
