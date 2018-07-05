#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST
from auto_config import password, user


def test_01_check_root_user_authentification():
    payload = {"username": user,
               "password": password}
    results = POST("/auth/check_user", payload)
    assert results.status_code == 200, results.text
