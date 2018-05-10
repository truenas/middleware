#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, DELETE


def test_01_creating_a_new_boot_environment():
    payload = {"name": "bootenv01", "source": "default"}
    results = POST("/bootenv", payload)
    assert results.status_code == 201, results.text


def test_02_look_new_bootenv_is_created():
    assert len(GET('/bootenv?name=bootenv01').json()) == 1


# Update tests
def test_03_Cloning_a_new_boot_environment_newbe2():
    payload = {"name": "bootenv02", "source": "bootenv01"}
    results = POST("/bootenv", payload)
    assert results.status_code == 200, results.text


# Delete tests
def test_04_Removing_a_boot_environment_newbe2():
    results = DELETE("/bootenv/id/bootenv02")
    assert results.status_code == 200, results.text
