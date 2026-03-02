import pytest

from middlewared.plugins.catalog.apps_util import custom_scale_version_checks


@pytest.mark.parametrize('min_version, max_version, sys_scale_version, expected', [
    (
        '21.0',
        '23.1',
        '22.01',
        ''
    ),
    (
        '22.15',
        '21.05',
        '22.01',
        'Your TrueNAS system version (22.01) is less than the minimum version (22.15) required by this application.'
    ),
    (
        '22.01',
        '23.01',
        '22.01',
        ''
    ),
    (
        '22.01',
        '23.02',
        '24.05',
        'Your TrueNAS system version (24.05) is greater than the maximum version (23.02) required by this application.'
    ),
    (
        '22.01',
        '21.03',
        'MASTER-SNAPSHOT',
        'Unable to determine your TrueNAS system version'
    ),
    (
        '24.10.2.2',
        None,
        '26.0.0-MASTER-20260215',
        ''
    ),
    (
        None,
        '25.04',
        '26.0.0-MASTER-20260215',
        'Your TrueNAS system version (26.0.0) is greater than the maximum version (25.04) required by this application.'
    ),
    (
        '24.10',
        '27.0',
        '26.0.0-MASTER-20260215',
        ''
    ),
])
def test_custom_scale_version(min_version, max_version, sys_scale_version, expected):
    result = custom_scale_version_checks(min_version, max_version, sys_scale_version)
    assert result == expected
