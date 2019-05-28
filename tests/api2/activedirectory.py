#!/usr/bin/env python3.6

import os
import sys
import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name
from config import *
from functions import GET, POST, PUT

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

dataset = f"{pool_name}/ad-bsd"
SMB_NAME = "TestShare"
SMB_PATH = f"/mnt/{pool_name}/{DATASET}"
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


def test_01_get_activedirectory_data():
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', list(ad_data_type.keys()))
def test_02_verify_activedirectory_data_type_of(data):
    assert isinstance(results.json()[data], ad_data_type[data]), results.text


def test_03_creating_dataset_for_smb():
    results = POST("/pool/dataset/", {"name": dataset})
    assert results.status_code == 200, results.text


@ad_test_cfg
def test_04_enabling_activedirectory():
    global payload, results
    payload = {
        "bindpw": ADPASSWORD,
        "bindname": ADUSERNAME,
        "domainname": BRIDGEDOMAIN,
        "netbiosname_a": BRIDGEHOST,
        "idmap_backend": "rid",
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text
