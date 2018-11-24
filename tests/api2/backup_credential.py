#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET


def test_01_check_backup_credential():
    results = GET("/backup/credential/")
    assert results.status_code == 200, results.text


# def test_02_creating_backup_credential():
#     payload = {"name": "string",
#                "provider": "AMAZON",
#                "attributes": {"additionalProp1": {}}}
#     results = POST("/backup/credential/", payload)
#     assert results.status_code == 200, results.text
