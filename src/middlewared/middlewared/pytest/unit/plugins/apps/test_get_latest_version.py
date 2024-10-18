import pytest

from middlewared.plugins.apps.version_utils import get_latest_version_from_app_versions
from middlewared.service import CallError


@pytest.mark.parametrize('versions, should_work, expected', [
    (
        {
            '1.1.9': {
                'healthy': True,
                'supported': True,
                'healthy_error': None,
                'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget/1.1.9',
                'last_update': '2024-10-02 18:57:15',
                'required_features': [
                    'definitions/certificate',
                    'definitions/port',
                    'normalize/acl',
                    'normalize/ix_volume'
                ],
            }
        },
        True,
        '1.1.9'
    ),
    (
        {
            '1.1.9': {
                'healthy': None,
                'supported': True,
                'healthy_error': None,
                'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget/1.1.9',
                'last_update': '2024-10-02 18:57:15',
                'required_features': [
                    'definitions/certificate',
                    'definitions/port',
                    'normalize/acl',
                    'normalize/ix_volume'
                ],
            }
        },
        False,
        None
    ),
    (
        {},
        False,
        None
    ),
    (
        {
            '1.1.9': {
                'healthy': None,
                'supported': True,
                'healthy_error': None,
                'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget/1.1.9',
                'last_update': '2024-10-02 18:57:15',
                'required_features': [
                    'definitions/certificate',
                    'definitions/port',
                    'normalize/acl',
                    'normalize/ix_volume'
                ],
            },
            '2.0.1': {
                'healthy': True,
                'supported': True,
                'healthy_error': None,
                'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget/2.0.1',
                'last_update': '2024-10-02 18:57:15',
                'required_features': [
                    'definitions/certificate',
                    'definitions/port',
                    'normalize/acl',
                    'normalize/ix_volume'
                ],
            }
        },
        True,
        '2.0.1'
    ),
])
def test_get_latest_version(versions, should_work, expected):
    if should_work:
        version = get_latest_version_from_app_versions(versions)
        assert version == expected
    else:
        with pytest.raises(CallError):
            get_latest_version_from_app_versions(versions)
