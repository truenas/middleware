#!/usr/bin/env python3.6

import os
import sys
import pytest
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name
from config import *
from functions import GET, POST, PUT, DELETE

ad_data_type = {
    'id': int,
    'domainname': str,
    'bindname': str,
    'bindpw': str,
    'ssl': str,
    'certificate': type(None),
    'verbose_logging': bool,
    'unix_extensions': bool,
    'allow_trusted_doms': bool,
    'use_default_domain': bool,
    'allow_dns_updates': bool,
    'disable_freenas_cache': bool,
    'site': type(None),
    'kerberos_realm': type(None),
    'kerberos_principal': str,
    'createcomputer': str,
    'timeout': int,
    'dns_timeout': int,
    'idmap_backend': str,
    'nss_info': type(None),
    'ldap_sasl_wrapping': str,
    'enable': bool,
    'netbiosname': str,
    'netbiosalias': list
}

ad_object_list = [
        "bindname",
        "domainname",
        "netbiosname",
        "idmap_backend",
        "enable"
]

if "BRIDGEHOST" in locals():
    MOUNTPOINT = f"/tmp/ad{BRIDGEHOST}"
dataset = f"{pool_name}/ad-bsd"
dataset_url = dataset.replace('/', '%2F')
SMB_NAME = "TestShare"
SMB_PATH = f"/mnt/{dataset}"
VOL_GROUP = "wheel"

Reason = "BRIDGEHOST, BRIDGEDOMAIN, ADPASSWORD, and ADUSERNAME are missing in "
Reason += "ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'

ad_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                      "BRIDGEDOMAIN" in locals(),
                                      "ADPASSWORD" in locals(),
                                      "ADUSERNAME" in locals(),
                                      "MOUNTPOINT" in locals()
                                      ]) is False, reason=Reason)


bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)


def test_01_get_activedirectory_data():
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', list(ad_data_type.keys()))
def test_02_verify_activedirectory_data_type_of_(data):
    assert isinstance(results.json()[data], ad_data_type[data]), results.text


def test_03_get_activedirectory_state():
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_04_get_activedirectory_started_before_starting_activedirectory():
    results = GET('/activedirectory/started/')
    assert results.status_code == 400, results.text


def test_05_creating_ad_dataset_for_smb():
    results = POST("/pool/dataset/", {"name": dataset})
    assert results.status_code == 200, results.text


@ad_test_cfg
def test_06_enabling_activedirectory():
    global payload, results
    payload = {
        "bindpw": ADPASSWORD,
        "bindname": ADUSERNAME,
        "domainname": BRIDGEDOMAIN,
        "netbiosname": BRIDGEHOST,
        "idmap_backend": "RID",
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text


@ad_test_cfg
def test_07_get_activedirectory_state():
    global results
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


@ad_test_cfg
def test_08_get_activedirectory_started():
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


@ad_test_cfg
def test_09_get_activedirectory_data():
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@ad_test_cfg
@pytest.mark.parametrize('data', ad_object_list)
def test_10_verify_activedirectory_data_of_(data):
    if data == 'domainname':
        assert results.json()[data].lower() == payload[data], results.text
    else:
        assert results.json()[data] == payload[data], results.text


def test_11_enabling_smb_service():
    payload = {
        "description": "Test FreeNAS Server",
        "guest": "nobody",
        "hostlookup": False,
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_12_Creating_a_SMB_share_on_SMB_PATH():
    payload = {
        "comment": "My Test SMB Share",
        "path": SMB_PATH,
        "name": SMB_NAME,
        "guestok": True,
        "vfsobjects": ["streams_xattr"]
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text


def test_13_enable_cifs_service():
    results = PUT("/service/id/cifs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_14_checking_to_see_if_clif_service_is_enabled():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is True, results.text


def test_15_starting_cifs_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/restart/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_16_checking_to_see_if_nfs_service_is_running():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


# put all code to disable and delete under here
@ad_test_cfg
def test_17_disabling_activedirectory():
    global payload, results
    payload = {
        "enable": False
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text


def test_18_disable_cifs_service_at_boot():
    results = PUT("/service/id/cifs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_19_checking_to_see_if_clif_service_is_enabled_at_boot():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is False, results.text


def test_20_stoping_clif_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_21_checking_if_cifs_is_stop():
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


def test_22_destroying_ad_dataset_for_smb():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
