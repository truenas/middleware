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
        '22.0',
        'Unable to determine your TrueNAS system version'
    )
])
def test_custom_scale_version(min_version, max_version, sys_scale_version, expected):
    result = custom_scale_version_checks(min_version, max_version, sys_scale_version)
    assert result == expected
