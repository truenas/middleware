#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST

url_path = "/legacy/system/debug/download/"


def test_01_Creating_diagnostic_file():
    payload = {"name": "newbe1", "source": "default"}
    results = POST("/system/debug/", payload)
    assert results.status_code == 200, results.text
    assert results.json()["url"] == url_path, results.text
