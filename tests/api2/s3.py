#!/usr/bin/env python3.6

# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT
from auto_config import ip


ENDPOINT = ip + ':9000'
ACCESS_KEY = 'ixsystems'
SECRET_KEY = 'ixsystems'


def test_01_update_s3_service():
    volumes = GET("/storage/volume/", api="1")
    if volumes:
        result = PUT('/s3/', {
            'bindip': '0.0.0.0',
            'bindport': 9000,
            'access_key': ACCESS_KEY,
            'secret_key': SECRET_KEY,
            'browser': True,
            'storage_path': volumes.json()[0]['mountpoint']
        })

        assert result.status_code == 200, result.text


def test_02_enable_s3_service():
    payload = {"enable": True}
    results = PUT("/service/id/s3/", payload)
    assert results.status_code == 200, results.text


def test_03_start_s3_service():
    result = POST(
        '/service/start/', {
            'service': 's3',
            'service-control': {
                'onetime': True
            }
        }
    )

    assert result.status_code == 200, result.text


def test_04_verify_s3_is_running():
    results = GET("/service/?service=s3")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_05_stop_iSCSI_service():
    result = POST(
        '/service/stop', {
            'service': 's3',
            'service-control': {
                'onetime': True
            }
        }
    )

    assert result.status_code == 200, result.text


def test_06_verify_s3_is_not_running():
    results = GET("/service/?service=s3")
    assert results.json()[0]["state"] == "STOPPED", results.text
