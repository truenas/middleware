#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST


def test_01_Creating_a_new_boot_environment_newbe1():
    payload = {"name": "newbe1", "source": "default"}
    assert POST("/system/bootenv/", payload) == 201
