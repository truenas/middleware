import pytest

from middlewared.plugins.reporting.utils import get_metrics_approximation, calculate_disk_space_for_netdata


@pytest.mark.parametrize('disk_count,core_count,interface_count,pool_count,expected_output', [
    (4, 2, 1, 2, {1: 370, 60: 4}),
    (1600, 32, 4, 4, {1: 44017, 60: 1600}),
    (10, 16, 2, 2, {1: 777, 60: 10}),
])
def test_netdata_metrics_count_approximation(disk_count, core_count, interface_count, pool_count, expected_output):
    assert get_metrics_approximation(disk_count, core_count, interface_count, pool_count) == expected_output


@pytest.mark.parametrize('disk_count,core_count,interface_count,pool_count,days,expected_output', [
    (4, 2, 1, 2, 7, 213),
    (1600, 32, 4, 4, 4, 14516),
    (10, 16, 2, 2, 3, 192),
    (1600, 32, 4, 4, 18, 65323),
])
def test_netdata_disk_space_approximation(disk_count, core_count, interface_count, pool_count, days, expected_output):
    assert calculate_disk_space_for_netdata(get_metrics_approximation(
        disk_count, core_count, interface_count, pool_count
    ), days) == expected_output
