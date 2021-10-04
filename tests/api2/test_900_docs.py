#!/usr/bin/env python3

# License: BSD

import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import SSH_TEST
from auto_config import ip, user, password


def test_core_get_methods(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    results = SSH_TEST("midclt call core.get_methods", user, password, ip)
    assert results['result'] is True, results
