#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST
from auto_config import ha, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')
source_list = []
source_dict = {}
sources = GET('/stats/get_sources/', controller_a=ha).json()
for source, types in sources.items():
    if 'interface-vnet0' not in source:
        source_list.append(source)


def test_01_get_stats_sources():
    results = GET('/stats/get_sources/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    global source_dict
    source_dict = results.json()


@pytest.mark.parametrize('source', source_list)
def test_02_get_stats_dataset_info_for_(source):
    for _type in source_dict[source]:
        payload = {'source': source, 'type': _type}
        results = POST('/stats/get_dataset_info/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict) is True


@pytest.mark.parametrize('source', source_list)
def test_03_get_stats_data_for_(source):
    for _type in source_dict[source]:
        payload1 = {'source': source, 'type': _type}
        results = POST('/stats/get_dataset_info/', payload1)
        assert results.status_code == 200, results.text
        info = results.json()
        assert isinstance(info, dict) is True
        payload2 = {
            'stats_list': [{
                'source': source,
                'type': _type,
                'dataset': list(info['datasets'].keys())[0],
            }],
        }
        results = POST('/stats/get_data/', payload2)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict) is True
