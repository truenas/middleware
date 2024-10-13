import textwrap

import pytest

from middlewared.plugins.catalog.apps_util import retrieve_cached_versions_data
from middlewared.service import CallError


@pytest.mark.parametrize('file, should_work', [
    (
        '''
        version: 1.0.1
        ''',
        False
    ),
    (
        '''
        {
            'versions': '1.0.1'
        }
        ''',
        False
    ),
    (
        None,
        False
    ),
    (
        textwrap.dedent(
            '''
            {
                "1.0.1": {
                    "name": "chia",
                    "categories": [],
                    "app_readme": null,
                    "location": "/mnt/mypool/ix-applications/catalogs/github_com_truenas_charts_git_master/charts/chia",
                    "healthy": true,
                    "supported": true,
                    "healthy_error": null,
                    "required_features": [],
                    "version": "1.0.1",
                    "human_version": "1.15.12",
                    "home": null,
                    "readme": null,
                    "changelog": null,
                    "last_update": "2024-10-09 00:00:00",
                    "app_metadata": {
                        "name": "chia",
                        "train": "stable",
                        "version": "1.0.1",
                        "app_version": "1.0.1",
                        "title": "chia",
                        "description": "desc",
                        "home": "",
                        "sources": [],
                        "maintainers": [],
                        "run_as_context": [],
                        "capabilities": [],
                        "host_mounts": []
                    },
                    "schema": {
                        "groups": [],
                        "questions": []
                    }
                }
            }
            '''
        ),
        True
    ),
])
def test_retrieve_caches_versions_data(mocker, file, should_work):
    mock_file = mocker.mock_open(read_data=file)
    mocker.patch('builtins.open', mock_file)
    if should_work:
        result = retrieve_cached_versions_data('/path/to/app', 'actual-budget')
        assert isinstance(result, dict)
    else:
        with pytest.raises(CallError):
            retrieve_cached_versions_data('/path/to/app', 'actual-budget')
