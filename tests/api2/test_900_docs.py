#!/usr/bin/env python3

# License: BSD

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import SSH_TEST
from auto_config import user, password


def test_core_get_methods(request):
    results = SSH_TEST("midclt call core.get_methods", user, password)
    assert results['result'] is True, results
