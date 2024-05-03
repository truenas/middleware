import pytest

from unittest.mock import Mock, patch

from middlewared.plugins.catalogs_linux.items_util import min_max_scale_version_check_update_impl


@pytest.mark.parametrize('version_details,supported,system_scale_version,result', [
    (
        {'chart_metadata': {'annotations': {'min_scale_version': '24.04'}}},
        False, '24.04-MASTER-20230928-144829',
        ''
    ),

    (
        {'chart_metadata': {'annotations': {'min_scale_version': '24.05'}}},
        False, '24.04-MASTER-20230928-144829',
        'Your TrueNAS system version (24.04) is less than the minimum version (24.05) required by this application.'
    ),

    (
        {'chart_metadata': {'annotations': {'min_scale_version': '22.03', 'max_scale_version': '25.10'}}},
        False, '24.04-MASTER-20230928-144829',
        ''
    ),

    (
        {'chart_metadata': {'annotations': {'min_scale_version': '22.03', 'max_scale_version': '23.10'}}},
        False, '24.04-MASTER-20230928-144829',
        'Your TrueNAS system version (24.04) is greater than the maximum version (23.10) required by this application.'
    ),

    (
        {'chart_metadata': {'annotations': {'min_scale_version': '24.05', 'max_scale_version': '25.10'}}},
        False, '24.04-MASTER-20230928-144829',
        'Your TrueNAS system version (24.04) is less than the minimum version (24.05) required by this application.'
    ),

    (
        {'chart_metadata': {'annotations': {'min_scale_version': '24.05', 'max_scale_version': '25.10'}}},
        False, '24.04-MASTER-20230928-144829',
        'Your TrueNAS system version (24.04) is less than the minimum version (24.05) required by this application.'
    ),

    (
        {'chart_metadata': {'annotations': {'min_scale_version': '23.10', 'max_scale_version': '25.10'}}},
        False, '24.04',
        ''
    ),

    (
        {'chart_metadata': {'annotations': {'min_scale_version': '22.03', 'max_scale_version': '23.10'}}},
        False, '24.04',
        'Your TrueNAS system version (24.04) is greater than the maximum version (23.10) required by this application.'
    ),

    (
        {'chart_metadata': {'annotations': {'min_scale_version': '24.05', 'max_scale_version': '25.10'}}},
        False, '24.04',
        'Your TrueNAS system version (24.04) is less than the minimum version (24.05) required by this application.'
    ),

    (
        {'chart_metadata': {'annotations': {'min_scale_version': '24.05', 'max_scale_version': '25.10'}}},
        False, '24.04',
        'Your TrueNAS system version (24.04) is less than the minimum version (24.05) required by this application.'
    ),

    (
        {'chart_metadata': {'annotations':  {'min_scale_version': '24.03'}}},
        False, '24.04',
        ''
    ),

    (
        {'chart_metadata': {'annotations': {'min_scale_version': '24.04'}}},
        False, '24.04',
        ''
    ),

    (
        {'chart_metadata': {'annotations': {'max_scale_version': '24.03'}}},
        False, '24.04',
        'Your TrueNAS system version (24.04) is greater than the maximum version (24.03) required by this application.'
    ),

    (
        {'chart_metadata': {'annotations': {'max_scale_version': '24.04'}}},
        False, '24.04',
        ''
    ),
])
def test_scale_version_compatibility_check(version_details, supported, system_scale_version, result):
    with patch('middlewared.plugins.catalogs_linux.items_util.sw_info', Mock(
        return_value={'version': system_scale_version}
    )):
        assert min_max_scale_version_check_update_impl(version_details, supported) == result
