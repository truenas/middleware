#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, DELETE


def test_01_Creating_a_new_boot_environment_newbe1():
    payload = {"name": "newbe1", "source": "default"}
    assert POST("/system/bootenv/", payload) == 201


# Update tests
def test_02_Cloning_a_new_boot_environment_newbe2():
    payload = {"name": "newbe2", "source": "newbe1"}
    assert POST("/system/bootenv/", payload) == 201


# Delete tests
def test_01_Removing_a_boot_environment_newbe2():
    assert DELETE("/system/bootenv/newbe2/") == 204
