#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, DELETE

pytestmark = pytest.mark.accounts


def test_01_deleting_user_shareuser(request):
    depends(request, ["shareuser"], scope="session")
    userid = GET('/user?username=shareuser').json()[0]['id']
    results = DELETE("/user/id/%s/" % userid, {"delete_group": True})
    assert results.status_code == 200, results.text
