#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, DELETE


def test_01_deleting_user_shareuser():
    userid = GET('/user?username=shareuser').json()[0]['id']
    results = DELETE("/user/id/%s/" % userid, {"delete_group": True})
    assert results.status_code == 200, results.text
