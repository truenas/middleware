from datetime import datetime, timedelta
import json
import requests
import time
import uuid

import pytest
import websocket

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, host, ssh

USERNAME = 'alex'
PASSWORD = 'password'
SHARE_NAME = 'alex'

pytestmark = pytest.mark.skip('Skip until we manage to add test systems to TrueNAS Connect')


@pytest.fixture(scope='module')
def share():
    call('webshare.update', {'search': True})
    call('service.control', 'START', 'webshare', job=True)
    try:
        with dataset('webshare') as ds:
            with user({
                'username': USERNAME,
                'full_name': 'Alex',
                'group_create': True,
                'password': PASSWORD,
            }) as u:
                ssh(f"echo Canary > /mnt/{ds}/test.txt")
                ssh(f"chown {u['uid']}:{u['group']['bsdgrp_gid']} /mnt/{ds}/test.txt")

                share = call('sharing.webshare.create', {'name': 'Share', 'path': f'/mnt/{ds}'})

                try:
                    yield {
                        'dataset': ds,
                    }
                finally:
                    call('sharing.webshare.delete', share['id'])

                    for i in range(30):
                        processes = call('pool.dataset.processes', ds)
                        if not processes:
                            break

                        time.sleep(1)
                    else:
                        pytest.fail(str(processes))

    finally:
        call('service.control', 'STOP', 'webshare', job=True)


class JSONRPCException(Exception):
    pass


def call_method(ws, method, params, *, call_id=None):
    if call_id is None:
        call_id = str(uuid.uuid4())

    ws.send(json.dumps({"jsonrpc": "2.0", "id": call_id, "method": method, "params": params}))
    while True:
        resp_opcode, msg = ws.recv_data()
        result = json.loads(msg.decode())
        if result.get("id") == call_id:
            break

    if "error" in result:
        raise JSONRPCException(result["error"])

    return result["result"]


def test_webshare(share):
    for i in range(30):
        try:
            auth_ws = websocket.create_connection(
                f"wss://{host().ip}:755/webshare/ws",
                sslopt={"cert_reqs": 0},
                timeout=30,
            )
            break
        except (ConnectionRefusedError, websocket.WebSocketBadStatusException):
            time.sleep(1)
    else:
        assert False, "Unable to establish websocket connection with webshare auth service"

    try:
        result = call_method(auth_ws, "login", {
            "username": USERNAME,
            "password": PASSWORD,
        }, call_id=1)  # {'code': -32700, 'message': 'Parse error'} when using string IDs

        for i in range(30):
            try:
                ws = websocket.create_connection(
                    f"wss://{host().ip}:755{result['websocket_url']}",
                    header={"Cookie": f"truenas_auth_token={result['auth_token']}"},
                    sslopt={"cert_reqs": 0},
                    timeout=30,
                )
                break
            except (ConnectionRefusedError, websocket.WebSocketBadStatusException):
                time.sleep(1)
        else:
            assert False, "Unable to establish websocket connection with webshare auth service"

        try:
            result = call_method(ws, "shares.list", {})
            assert len(result["shares"]) == 1
            assert result["shares"][0]["name"] == "Share"

            result = call_method(ws, "directory.list", {
                "path": "/Share",
                "fileHandle": result["shares"][0]["fileHandle"],
                "showHidden": False,
                "offset": 0,
                "limit": 1000,
                "sortBy": "name",
                "sortOrder": "asc",
                "metadata": "minimal"
            })
            assert result["started"]

            exc = None
            for i in range(30):
                try:
                    result = call_method(ws, "file.truesearch", {
                        "query": "test",
                        "path": "/Share",
                        "searchLocation": "current",
                        "maxResults": 50
                    })

                    if result["items"]:
                        break
                except JSONRPCException as e:
                    exc = e
                    time.sleep(1)
            else:
                if exc is not None:
                    raise exc

                assert False, result

            assert len(result["items"]) == 1
            assert result["items"][0]["name"] == "test.txt"

            result = call_method(ws, "share.createDownload", {
                "path": "/share/test.txt",
                "fileHandle": result["items"][0]["fileHandle"],
                "expiry": (datetime.now().replace(microsecond=0, tzinfo=None) + timedelta(days=1)).isoformat() + "Z",
                "maxDownloads": 1,
                "password": None,
            })

            r = requests.get(f"https://{host().ip}:756/api/download/{result['shareId']}/file", verify=False)
            assert r.text == "Canary\n"
        finally:
            ws.close()
    finally:
        auth_ws.close()


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
    assert webshare['share_name'] == 'Share'
