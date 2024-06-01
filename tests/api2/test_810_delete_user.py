#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

from pytest_dependency import depends
from test_011_user import UserAssets

from functions import DELETE, GET


def test_01_deleting_user_shareuser(request):
    depends(request, [UserAssets.ShareUser01['depends_name']], scope="session")
    userid = GET('/user?username=shareuser').json()[0]['id']
    results = DELETE("/user/id/%s/" % userid, {"delete_group": True})
    assert results.status_code == 200, results.text
