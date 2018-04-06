#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET_OUTPUT


def test_01_Creating_diagnostic_file():
    payload = {"name": "newbe1", "source": "default"}
    assert POST("/system/debug/", payload) == 200


def test_02_Verify_that_API_returns_WWW_download_path():
    assert GET_OUTPUT("/system/debug/", "url") == "/system/debug/download/"
