#!/usr/bin/env python3

# License: BSD

import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, DELETE
from auto_config import ip, pool_name


ENDPOINT = ip + ':9000'
ACCESS_KEY = 'ixsystems'
SECRET_KEY = 'ixsystems'

dataset = f"{pool_name}/s3"
dataset_url = dataset.replace('/', '%2F')
dataset_path = "/mnt/" + dataset


def test_01_creating_dataset_for_s3():
    results = POST("/pool/dataset/", {"name": dataset})
    assert results.status_code == 200, results.text


def test_02_update_s3_service():
    payload = {
        'bindip': '0.0.0.0',
        'bindport': 9000,
        'access_key': ACCESS_KEY,
        'secret_key': SECRET_KEY,
        'browser': True,
        'storage_path': dataset_path
    }
    result = PUT('/s3/', payload)
    assert result.status_code == 200, result.text


def test_03_enable_s3_service():
    payload = {
        "enable": True
    }
    results = PUT("/service/id/s3/", payload)
    assert results.status_code == 200, results.text


def test_04_start_s3_service():
    result = POST(
        '/service/start/', {
            'service': 's3',
            'service-control': {
                'onetime': True
            }
        }
    )

    assert result.status_code == 200, result.text
    sleep(1)


def test_05_verify_s3_is_running():
    results = GET("/service/?service=s3")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_06_stop_iSCSI_service():
    result = POST(
        '/service/stop/', {
            'service': 's3',
            'service-control': {
                'onetime': True
            }
        }
    )

    assert result.status_code == 200, result.text
    sleep(1)


def test_07_verify_s3_is_not_running():
    results = GET("/service/?service=s3")
    assert results.json()[0]["state"] == "STOPPED", results.text


def test_08_delete_s3_dataset():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
