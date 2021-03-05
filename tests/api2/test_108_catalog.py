
import os
import pytest
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, DELETE
from auto_config import ha, scale, dev_test

if dev_test:
    reason = 'Skip for testing'
else:
    reason = 'Skipping test for HA' if ha else 'Skipping test for CORE'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(ha or not scale or dev_test, reason=reason)

official_repository = 'https://github.com/truenas/charts.git'
unofficial_repository = 'https://github.com/ericbsd/charts.git'
official_chart = ['plex', 'nextcloud', 'minio', 'ix-chart', 'ipfs']
unofficial_charts = [
    'zwavejs2mqtt',
    'unifi',
    'tvheadend',
    'truecommand',
    'transmission',
    'traefik',
    'tautulli',
    'sonarr',
    'sabnzbd',
    'readarr',
    'radarr',
    'qbittorrent',
    'organizr',
    'ombi',
    'nzbhydra',
    'nzbget',
    'node-red',
    'navidrome',
    'lychee',
    'lidarr',
    'lazylibrarian',
    'kms',
    'jellyfin',
    'jackett',
    'home-assistant',
    'heimdall',
    'handbrake',
    'grocy',
    'gaps',
    'freshrss',
    'esphome',
    'deluge',
    'collabora-online',
    'calibre-web',
    'bazarr'
]

unofficial_catalog = {
    'label': 'TRUECHARTS',
    'repository': unofficial_repository,
    'branch': 'master',
    'builtin': False,
    'preferred_trains': ['charts'],
    'location': '/tmp/ix-applications/catalogs/github_com_ericbsd_charts_git_master',
    'id': 'TRUECHARTS'
}


def test_01_get_catalog_list():
    results = GET('/catalog/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_02_search_for_official_catalog_with_the_label():
    results = GET('/catalog/?label=OFFICIAL')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert results.json()[0]['id'] == 'OFFICIAL', results.text


def test_03_get_official_catalog_with_id():
    results = GET('/catalog/id/OFFICIAL/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['label'] == 'OFFICIAL', results.text


def test_04_verify_official_catalog_repository_with_id():
    results = GET('/catalog/id/OFFICIAL/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['repository'] == official_repository, results.text


def test_05_verify_official_catalog_repository_with_id():
    results = GET('/catalog/id/OFFICIAL/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['repository'] == official_repository, results.text


@pytest.mark.parametrize('chart', official_chart)
def test_06_get_official_catalog_item(chart):
    payload = {
        "label": "OFFICIAL",
        "options": {
            "cache": True
        }
    }
    results = POST('/catalog/items/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['charts'][chart]['name'] == chart


def test_07_set_an_unofficial_catalog():
    global payload, results
    payload = {
        "force": False,
        "preferred_trains": ['charts'],
        "label": "TRUECHARTS",
        "repository": unofficial_repository,
        "branch": "master"
    }
    results = POST('/catalog/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('key', list(unofficial_catalog.keys()))
def test_08_verify_an_unofficial_catalog_object(key):
    assert results.json()[key] == unofficial_catalog[key], results.text


@pytest.mark.parametrize('key', list(unofficial_catalog.keys()))
def test_09_verify_truechart_catalog_object(key):
    results = GET('/catalog/id/TRUECHARTS/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()[key] == unofficial_catalog[key], results.text


def test_25_delete_truechart_catalog():
    results = DELETE('/catalog/id/TRUECHARTS/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool), results.text
    assert results.json() is True, results.text
