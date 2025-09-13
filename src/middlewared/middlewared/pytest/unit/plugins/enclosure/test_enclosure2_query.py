# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import dataclasses
import json
import os
import pathlib
from unittest.mock import Mock

import pytest

from middlewared.pytest.unit.middleware import Middleware
from middlewared.plugins.enclosure_.enclosure2 import Enclosure2Service

test_case_dir = pathlib.Path(os.path.dirname(os.path.realpath(__file__))) / 'test-cases'
test_case_paths = [i for i in test_case_dir.iterdir() if i.is_dir()]
test_case_names = [i.name for i in test_case_paths]


@dataclasses.dataclass
class Enc2Mocked:
    chassis: str
    labels: dict
    dmi: dict
    ses: list[dict]
    nvme: list[dict]


@dataclasses.dataclass
class Enc2Expected:
    expected: list[dict]


def hookit(obj):
    try:
        # we need to do this because the keys that
        # we're reading have all been cast to string
        # since the json spec defines keys as being
        # of type string. However, python doesn't
        # have such limitation. If you use, however,
        # the in-built json.dumps/loads module, it
        # will convert all those integer based keys
        # to strings for you. We expect integers as
        # the keys so convert them back
        return {int(k): v for k, v in obj.items()}
    except ValueError:
        # just means top-level key isn't an int so
        # return the value as-is
        return obj


@pytest.fixture(params=test_case_paths, ids=test_case_names)
def enc2_data(request):
    test_dir: pathlib.Path = request.param

    with open(test_dir / 'mocked.json') as f:
        mocked_data = json.load(f, object_hook=hookit)

    with open(test_dir / 'expected.json') as f:
        expected_data = json.load(f, object_hook=hookit)

    return Enc2Mocked(**mocked_data), Enc2Expected(expected_data)


def test_enclosure2_query(enc2_data):
    enc2_mocked = enc2_data[0]
    enc2_expected = enc2_data[1]

    e = Enclosure2Service(Mock())
    e.middleware = Middleware()
    e.middleware['truenas.get_chassis_hardware'] = Mock(return_value=enc2_mocked.chassis)
    e.middleware['truenas.is_ix_hardware'] = Mock(return_value=True)
    e.middleware['enclosure.label.get_all'] = Mock(return_value=enc2_mocked.labels)
    e.middleware['system.dmidecode_info'] = Mock(return_value=enc2_mocked.dmi)
    e.middleware['jbof.query'] = Mock(return_value=[])
    e.middleware['enclosure2.map_jbof'] = Mock(return_value=[])
    e.get_ses_enclosures = Mock(return_value=enc2_mocked.ses)
    e.map_nvme = Mock(return_value=enc2_mocked.nvme)
    e.map_jbof = Mock(return_value=[])
    assert e.query() == enc2_expected.expected
