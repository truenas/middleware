#!/usr/bin/env python3
# License: BSD

import pytest

from middlewared.test.integration.utils import call, ssh

import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
TIMEZONE = "America/New_York"


def test_01_get_system_general():
    call("system.general.config")

def test_02_get_system_general_language_choices():
    call("system.general.language_choices")


def test_03_get_system_general_timezone_choices():
    results = call("system.general.timezone_choices")
    assert TIMEZONE in results


def test_04_get_system_general_country_choices():
    call("system.general.country_choices")


def test_05_get_system_general_kbdmap_choices():
    call("system.general.kbdmap_choices")


def test_06_Setting_timezone():
    call("system.general.update", {"timezone": TIMEZONE})


def test_07_Checking_timezone_using_api():
    results = call("system.general.config")
    assert results['timezone'] == TIMEZONE


def test_08_Checking_timezone_using_ssh(request):
    results = ssh(f'diff /etc/localtime /usr/share/zoneinfo/{TIMEZONE}')
    assert results == ""
