#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET


def test_01_Creating_diagnostic_file():
    payload = {"name": "newbe1", "source": "default"}
    results = POST("/system/debug/", payload)
    assert results.status_code == 200, results.text


def test_02_Verify_that_API_returns_WWW_download_path():
    results = GET("/system/debug/")
    assert results.json()["url"] == "/system/debug/download/", results.text
