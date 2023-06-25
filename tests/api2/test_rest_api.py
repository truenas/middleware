# -*- coding=utf-8 -*-
import urllib.parse

from middlewared.test.integration.utils import call

import os
import sys
sys.path.append(os.getcwd())
from functions import GET


def test_non_numeric_identifiers():
    disk = call('disk.query')[0]
    results = GET(f'/disk/id/{urllib.parse.quote(disk["identifier"])}/')
    assert results.status_code == 200, results.text
