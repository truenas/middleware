from unittest.mock import Mock

import pytest

from middlewared.plugins.device_.device_info import DeviceService


@pytest.mark.parametrize("host_type,disk_data,get_rotation_rate,result", [
    (None, {"rota": True}, Mock(return_value=7200), ("HDD", 7200)),
    (None, {"rota": True}, Mock(return_value=None), ("SSD", None)),
    (None, {"rota": False}, Mock(side_effect=RuntimeError()), ("SSD", None)),
    ("QEMU", {"rota": True}, Mock(side_effect=RuntimeError()), ("HDD", None)),
])
def test_get_type_and_rotation_rate(host_type, disk_data, get_rotation_rate, result):
    d = DeviceService(None)
    d.HOST_TYPE = host_type
    d._get_rotation_rate = get_rotation_rate
    assert d._get_type_and_rotation_rate(disk_data, None) == result
