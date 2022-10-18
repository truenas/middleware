#!/usr/bin/env python3

# License: BSD

import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET
from contextlib import contextmanager

try:
    from config import NIS_DOMAIN, NIS_SERVER
except ImportError:
    Reason = 'NIS_DOMAIN or NIS_SERVER is missing from config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)
else:
    from auto_config import dev_test
    # comment pytestmark for development testing with --dev-test
    pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


@contextmanager
def enable_nis_domain():
    results = PUT("/nis/", {
        'domain': NIS_DOMAIN,
        'servers': [NIS_SERVER],
        'enable': True
    })
    assert results.status_code == 200, results.text
    try:
        results = GET('/nis/')
        assert results.status_code == 200, results.text
        yield results.json()
    finally:
        results = PUT("/nis/", {
            'domain': '',
            'servers': [],
            'enable': False
        })
        assert results.status_code == 200, results.text


def test_01_check_nis():
    with enable_nis_domain() as c:
        # Verify that parameters set as expected
        assert c['domain'] == NIS_DOMAIN
        assert c['servers'] == [NIS_SERVER]

        # Verfiy that NIS state is healthy
        results = GET('/nis/get_state')
        assert results.status_code == 200, results.text
        assert results.json() == 'HEALTHY'
        sleep(5)

        # Verify that NIS users are in cache
        results = GET('/user', payload={
            'query-filters': [['local', '=', False]],
            'query-options': {'extra': {"search_dscache": True}},
        })
        assert results.status_code == 200, results.text
        assert len(results.json()) > 0, results.text

        # Verify that NIS groups are in cache
        results = GET('/group', payload={
            'query-filters': [['local', '=', False]],
            'query-options': {'extra': {"search_dscache": True}},
        })
        assert results.status_code == 200, results.text
        assert len(results.json()) > 0, results.text

    results = GET('/nis/')
    assert results.status_code == 200, results.text
    conf = results.json()
    assert conf['domain'] == ''
    assert conf['servers'] == []
    assert conf['enable'] is False
