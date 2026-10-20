from datetime import datetime, timedelta

import pytest
import requests

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.webshare import (
    LINK_PORT,
    WebshareError,
    webshare_server,
    webshare_session,
    webshare_share,
)
from middlewared.test.integration.utils import call, host, poll, ssh

USERNAME = 'alex'
PASSWORD = 'password'
SHARE_NAME = 'Share'


@pytest.fixture(scope='module')
def share():
    with entitled('WEBSHARE'), entitled('TRUESEARCH'):
        search = call('webshare.config')['search']
        call('webshare.update', {'search': True})
        try:
            with webshare_server():
                with dataset('webshare') as ds:
                    with user({
                        'username': USERNAME,
                        'full_name': 'Alex',
                        'group_create': True,
                        'password': PASSWORD,
                        'webshare': True,
                    }) as u:
                        ssh(f"echo Canary > /mnt/{ds}/test.txt")
                        ssh(f"chown -R {u['uid']}:{u['group']['bsdgrp_gid']} /mnt/{ds}")

                        with webshare_share(f'/mnt/{ds}', SHARE_NAME) as webshare:
                            # Verify dataset and relative_path resolution
                            assert webshare['dataset'] == ds
                            assert webshare['relative_path'] == ''

                            yield {
                                'dataset': ds,
                                'id': webshare['id'],
                            }

                        poll(
                            lambda: call('pool.dataset.processes', ds),
                            condition=lambda processes: not processes,
                            timeout=30,
                            message=f'{ds}: Webshare still holds the dataset',
                        )
        finally:
            call('webshare.update', {'search': search})


def test_webshare(share):
    with webshare_session(USERNAME, PASSWORD) as session:
        shares = session.shares()
        assert list(shares) == [SHARE_NAME]

        handle = shares[SHARE_NAME]['fileHandle']
        result = session.call('directory.list', {
            "path": f"/{SHARE_NAME}",
            "fileHandle": handle,
            "showHidden": False,
            "offset": 0,
            "limit": 1000,
            "sortBy": "name",
            "sortOrder": "asc",
            "metadata": "minimal"
        })
        assert result['started']

        def search():
            try:
                return session.call('file.truesearch', {
                    "query": "test",
                    "path": f"/{SHARE_NAME}",
                    "searchLocation": "current",
                    "maxResults": 50
                })
            except WebshareError as e:
                return e

        result = poll(
            search,
            condition=lambda value: not isinstance(value, WebshareError) and value['items'],
            timeout=30,
            message='TrueSearch did not index the share',
        )
        assert len(result['items']) == 1
        assert result['items'][0]['name'] == 'test.txt'

        result = session.call('share.createDownload', {
            "path": f"/{SHARE_NAME}/test.txt",
            "fileHandle": result['items'][0]['fileHandle'],
            "expiry": (datetime.now().replace(microsecond=0, tzinfo=None) + timedelta(days=1)).isoformat() + "Z",
            "maxDownloads": 1,
            "password": None,
        })

        r = requests.get(
            f"https://{host().ip}:{LINK_PORT}/api/download/{result['shareId']}/file", verify=False
        )
        assert r.text == "Canary\n"


def test_webshare_dataset_details(share):
    """Test that webshare details appear in pool.dataset.details"""
    details = call('pool.dataset.details')

    # Find the dataset that has the webshare
    webshare_dataset = None
    for ds in details:
        if ds['id'] == share['dataset']:
            webshare_dataset = ds
            break
        # Check children recursively
        for child in ds.get('children', []):
            if child['id'] == share['dataset']:
                webshare_dataset = child
                break

    assert webshare_dataset is not None, f"Dataset {share['dataset']} not found in details"

    # Verify webshare_shares field exists and contains our share
    assert 'webshare_shares' in webshare_dataset, "webshare_shares field not found in dataset details"

    webshare_shares = webshare_dataset['webshare_shares']
    assert len(webshare_shares) == 1, f"Expected 1 webshare, found {len(webshare_shares)}"

    webshare = webshare_shares[0]
    assert webshare['enabled'] is True
    assert webshare['path'] == f"/mnt/{share['dataset']}"
    assert webshare['share_name'] == SHARE_NAME


def test_writable_share_accepts_writes(share):
    with webshare_session(USERNAME, PASSWORD) as session:
        entry = session.shares()[SHARE_NAME]
        assert entry['readonly'] is False

        result = session.call('directory.create', {
            "path": f"/{SHARE_NAME}/writable",
            "parentDirHandle": entry['fileHandle'],
        })
        assert result['success']

        ssh(f"rmdir /mnt/{share['dataset']}/writable")


def test_readonly_share_refuses_writes_and_still_reads(share):
    assert call('sharing.webshare.update', share['id'], {'readonly': True})['readonly'] is True
    try:
        # A session keeps the configuration it started with, so this one starts after the update.
        with webshare_session(USERNAME, PASSWORD) as session:
            entry = session.shares()[SHARE_NAME]
            assert entry['readonly'] is True

            with pytest.raises(WebshareError) as ve:
                session.call('directory.create', {
                    "path": f"/{SHARE_NAME}/denied",
                    "parentDirHandle": entry['fileHandle'],
                })

            assert ve.value.message == f"Share '{SHARE_NAME}' is read-only"
            assert ve.value.data['reason'] == 'share_read_only'
            assert ssh(f"ls /mnt/{share['dataset']}") == "test.txt\n"

            result = session.call('directory.list', {
                "path": f"/{SHARE_NAME}",
                "fileHandle": entry['fileHandle'],
                "showHidden": False,
                "offset": 0,
                "limit": 1000,
                "sortBy": "name",
                "sortOrder": "asc",
                "metadata": "minimal"
            })
            assert result['started']
    finally:
        call('sharing.webshare.update', share['id'], {'readonly': False})


def test_webshare_no_access(share):
    with user({
        'username': 'invalid_webshare',
        'full_name': 'Alex',
        'group_create': True,
        'password': 'invalid_webshare',
        'webshare': False,
    }):
        with pytest.raises(WebshareError) as ve:
            with webshare_session('invalid_webshare', 'invalid_webshare'):
                pass

        assert ve.value.error == {'code': -32001, 'message': 'Authentication failed'}
