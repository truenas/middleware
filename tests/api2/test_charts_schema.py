import pytest
import secrets
import time

from pytest_dependency import depends

from middlewared.client.client import ValidationErrors
from middlewared.test.integration.assets.apps import chart_release
from middlewared.test.integration.assets.catalog import catalog

pytestmark = pytest.mark.apps


def test_text_schema(request):
    depends(request, ['setup_kubernetes'], scope='session')
    with catalog({
        'force': True,
        'preferred_trains': ['charts'],
        'label': 'TESTTEXT',
        'repository': 'https://github.com/truenas/charts.git',
        'branch': 'ix-text-schema-test'
    }) as catalog_obj:
        with chart_release({
            'catalog': catalog_obj['label'],
            'item': 'plex',
            'release_name': 'plex',
            'train': 'charts',
            'version': '1.7.59',
            'values': {'testtext': 'random-text'},
        }) as chart_release_obj:
            time.sleep(5)
            assert chart_release_obj['config']['testtext'] == 'random-text'


def test_text_schema_max_length(request):
    depends(request, ['setup_kubernetes'], scope='session')
    with catalog({
        'force': True,
        'preferred_trains': ['charts'],
        'label': 'TESTTEXT',
        'repository': 'https://github.com/truenas/charts.git',
        'branch': 'ix-text-schema-test'
    }) as catalog_obj:
        with pytest.raises(ValidationErrors) as ve:
            with chart_release({
                'catalog': catalog_obj['label'],
                'item': 'plex',
                'release_name': 'plex',
                'train': 'charts',
                'version': '1.7.59',
                'values': {'testtext': secrets.token_hex(2 * 1024 * 1024 // 2)},
            }):
                assert ve.value.errors[0].errmsg == (
                    'values.testtext: The value may not be longer than 1048576 characters'
                )
