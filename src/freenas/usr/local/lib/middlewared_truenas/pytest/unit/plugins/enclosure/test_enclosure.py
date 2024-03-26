# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import glob
import os

import pytest

from middlewared.plugins.enclosure import Enclosure


@pytest.mark.parametrize("data,model", [
    (open(f).read(), os.path.basename(f)[:-4])
    for f in glob.glob(os.path.dirname(__file__) + "/getencstat/*.txt")
])
def test__enclosure_model(data, model):
    assert Enclosure(0, data, {}).model == model


def test__element_group_descriptor():
    with open(os.path.dirname(__file__) + "/getencstat/Z Series.txt") as f:
        data = f.read()

    enclosure = Enclosure(0, data, {})

    assert enclosure.descriptors["Cooling"] == "SD_9GV12P1J_12R6K4"
