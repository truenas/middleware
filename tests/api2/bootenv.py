#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os
from time import sleep

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, DELETE, GET, PUT


def test_01_creating_a_new_boot_environment():
    payload = {"name": "bootenv01", "source": "default"}
    results = POST("/bootenv/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_02_look_new_bootenv_is_created():
    assert len(GET('/bootenv?name=bootenv01').json()) == 1


def test_03_activate_bootenv01():
    payload = None
    results = POST("/bootenv/id/bootenv01/activate/", payload)
    assert results.status_code == 200, results.text


# Update tests
def test_04_cloning_a_new_boot_environment():
    payload = {"name": "bootenv02", "source": "bootenv01"}
    results = POST("/bootenv/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_05_activate_bootenv02():
    payload = None
    results = POST("/bootenv/id/bootenv02/activate/", payload)
    assert results.status_code == 200, results.text


def test_06_change_boot_environment_name():
    payload = {"name": "bootenv03"}
    results = PUT("/bootenv/id/bootenv01/", payload)
    assert results.status_code == 200, results.text


def test_07_set_keep_attribute_true():
    payload = {"keep": True}
    results = POST("/bootenv/id/bootenv03/set_attribute/", payload)
    assert results.status_code == 200, results.text


def test_08_activate_bootenv03():
    payload = None
    results = POST("/bootenv/id/bootenv03/activate/", payload)
    assert results.status_code == 200, results.text


# Delete tests
def test_09_removing_a_boot_environment_02():
    results = DELETE("/bootenv/id/bootenv02/")
    assert results.status_code == 200, results.text


def test_10_set_keep_attribute_true():
    payload = {"keep": False}
    results = POST("/bootenv/id/bootenv03/set_attribute/", payload)
    assert results.status_code == 200, results.text


def test_11_activate_default():
    payload = None
    results = POST("/bootenv/id/default/activate/", payload)
    assert results.status_code == 200, results.text


def test_12_removing_a_boot_environment_03():
    results = DELETE("/bootenv/id/bootenv03/")
    assert results.status_code == 200, results.text
