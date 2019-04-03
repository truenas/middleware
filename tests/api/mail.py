#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET


def test_01_Configuring_settings():
    payload = {"fromemail": "william.spam@ixsystems.com",
               "outgoingserver": "mail.ixsystems.com",
               "pass": "changeme",
               "port": 25,
               "security": "PLAIN",
               "smtp": True,
               "user": "william.spam@ixsystems.com"}
    results = PUT("/mail/", payload)
    assert results.status_code == 200, results.text


def test_02_look_fromemail_settings_change():
    results = GET("/mail/")
    assert results.json()["fromemail"] == "william.spam@ixsystems.com"


def test_03_look_outgoingserver_settings_change():
    results = GET("/mail/")
    assert results.json()["outgoingserver"] == "mail.ixsystems.com"


def test_04_look_pass_settings_change():
    results = GET("/mail/")
    assert results.json()["pass"] == "changeme"


def test_05_look_port_settings_change():
    results = GET("/mail/")
    assert results.json()["port"] == 25


def test_06_look_security_settings_change():
    results = GET("/mail/")
    assert results.json()["security"] == "PLAIN"


def test_07_look_smtp_settings_change():
    results = GET("/mail/")
    assert results.json()["smtp"] is True


def test_08_look_user_settings_change():
    results = GET("/mail/")
    assert results.json()["user"] == "william.spam@ixsystems.com"
