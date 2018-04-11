#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT
from config import *
Reason = "NOIPUSERNAME, NOIPPASSWORD and NOIPHOST are missing "
Reason += "in ixautomation.conf"

noip_test_cfg = pytest.mark.skipif(all(["NOIPUSERNAME" in locals(),
                                        "NOIPPASSWORD" in locals(),
                                        "NOIPHOST" in locals()
                                        ]) is False, reason=Reason)


@noip_test_cfg
def test_01_Updating_Settings_for_NO_IP(self):
    payload = {"ddns_password": NOIPPASSWORD,
               "ddns_username": NOIPUSERNAME,
               "ddns_provider": "default@no-ip.com",
               "ddns_domain": NOIPHOST}
    results = PUT("/services/dynamicdns/", payload)
    assert results.status_code == 200, results.text
