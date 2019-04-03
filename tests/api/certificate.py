#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET


def test_01_get_certificate_query():
    results = GET('/certificate/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
