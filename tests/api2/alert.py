#!/usr/bin/env python3

import os
import sys
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, SSH_TEST
from auto_config import ip, password, user, pool_name


def test_01_get_alert_list():
    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_02_get_alert_list_categories():
    results = GET("/alert/list_categories/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert results.json(), results.json()


def test_03_get_alert_list_policies():
    results = GET("/alert/list_policies/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert results.json(), results.json()


def test_04_degrading_a_pool_to_create_an_alert():
    global gptid
    get_pool = GET(f"/pool/?name={pool_name}").json()[0]
    gptid = get_pool['topology']['data'][0]['path'].replace('/dev/', '')
    cmd = f'zinject -d {gptid} -A fault {pool_name}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_05_ensure_the_pool_is_degraded():
    cmd = f'zpool status {pool_name} | grep {gptid}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'DEGRADED' in results['output'], results['output']


def test_06_wait_for_the_alert():
    results = GET("/alert/list/?source=VolumeStatus")
    timeout = 0
    while not results.json():
        results = GET("/alert/list/?source=VolumeStatus")
        if timeout == 60:
            break
        timeout += 1
        sleep(1)
    assert results.json(), results.text


def test_07_verify_degraded_pool_alert_list_exist_and_get_id():
    global alert_id
    results = GET("/alert/list/?source=VolumeStatus")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    alert_id = results.json()[0]['id']
    assert results.json()[0]['args']['volume'] == pool_name, results.text
    assert results.json()[0]['args']['state'] == 'DEGRADED', results.text
    assert results.json()[0]['level'] == 'CRITICAL', results.text


def test_08_dimiss_the_alert():
    results = POST("/alert/dismiss/", alert_id)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), type(None)), results.text


def test_09_verify_the_alert_is_dismissed():
    results = GET(f"/alert/list/?id={alert_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert results.json()[0]['dismissed'] is True, results.text


def test_10_restore_the_alert():
    results = POST("/alert/restore/", alert_id)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), type(None)), results.text


def test_11_verify_the_alert_is_restored():
    results = GET(f"/alert/list/?id={alert_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert results.json()[0]['dismissed'] is False, results.text


def test_12_clear_the_pool_degradation():
    cmd = f'zpool clear {pool_name}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_13_ensure_the_pool_is_not_degraded():
    cmd = f'zpool status {pool_name} | grep {gptid}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'DEGRADED' not in results['output'], results['output']


def test_14_wait_for_the_alert_to_dissapear():
    results = GET("/alert/list/?source=VolumeStatus")
    timeout = 0
    while results.json():
        results = GET("/alert/list/?source=VolumeStatus")
        if timeout == 60:
            break
        timeout += 1
        sleep(1)
    assert not results.json(), results.text
