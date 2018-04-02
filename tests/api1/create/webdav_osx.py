#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET_OUTPUT

DATASET = "webdavshare"
DATASET_PATH = "/mnt/tank/%s/" % DATASET
SHARE_NAME = "webdavshare"
SHARE_USER = "webdav"
SHARE_PASS = "davtest"


def test_01_Creating_dataset_for_WebDAV_use():
    assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201


def test_02_Changing_permissions_on_DATASET_PATH():
    payload = {"mp_path": DATASET_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel"}
    assert PUT("/storage/permission/", payload) == 201


def test_03_Creating_WebDAV_share_on_DATASET_PATH():
    payload = {"webdav_name": SHARE_NAME,
               "webdav_comment": "Auto-created by API tests",
               "webdav_path": DATASET_PATH}
    assert POST("/sharing/webdav/", payload) == 201


def test_04_Starting_WebDAV_service():
    assert PUT("/services/services/webdav/", {"srv_enable": True}) == 200


def test_05_Verifying_that_the_WebDAV_service_has_started():
    assert GET_OUTPUT("/services/services/webdav",
                      "srv_state") == "RUNNING"


def test_06_Stopping_WebDAV_service():
    assert PUT("/services/services/webdav/", {"srv_enable": False}) == 200


def test_07_Verifying_that_the_WebDAV_service_has_stopped():
    assert GET_OUTPUT("/services/services/webdav",
                      "srv_state") == "STOPPED"
