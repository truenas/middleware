import binascii
import os
import pytest


def _check():
    if (
        'BACKUP_AWS_ACCESS_KEY' not in os.environ or
        'BACKUP_AWS_SECRET_KEY' not in os.environ or
        'BACKUP_AWS_BUCKET' not in os.environ or
        'BACKUP_AWS_REGION' not in os.environ
    ):
        pytest.skip("No credentials")


def _get_pool(conn):
    req = conn.rest.get('pool')
    assert req.status_code == 200

    pools = req.json()
    if len(pools) == 0:
        pytest.skip("No pool found")
    else:
        return pools[0]


@pytest.fixture(scope='module')
def creds():
    return {}


def test_backup_001_credential_query(conn):
    req = conn.rest.get('backup/credential')
    assert req.status_code == 200
    assert isinstance(req.json(), list) is True


def test_backup_002_credential_create(conn, creds):
    _check()
    req = conn.rest.post('backup/credential', data=[{
        'name': 'backtestcreds',
        'provider': 'AMAZON',
        'attributes': {
            'access_key': os.environ['BACKUP_AWS_ACCESS_KEY'],
            'secret_key': os.environ['BACKUP_AWS_SECRET_KEY'],
        },
    }])
    assert req.status_code == 200
    creds['credid'] = req.json()
    assert isinstance(creds['credid'], int) is True


def test_backup_003_credential_update(conn, creds):
    _check()
    req = conn.rest.post('backup/credential', data=[{
        'name': 'back_test_creds',
        'provider': 'AMAZON',
        'attributes': {
            'access_key': os.environ['BACKUP_AWS_ACCESS_KEY'],
            'secret_key': os.environ['BACKUP_AWS_SECRET_KEY'],
        },
    }])
    assert req.status_code == 200


def test_backup_010_create(conn, creds):
    _check()

    pool = _get_pool(conn)

    conn.ws.call('filesystem.file_receive', f'/mnt/{pool["name"]}/s3_test/foo', binascii.b2a_base64(b'bar').decode().strip())

    req = conn.rest.post('backup', data=[{
        "description": "desc",
        "direction": "PUSH",
        "path": f"/mnt/{pool['name']}/s3_test",
        "credential": creds['credid'],
        "minute": "00",
        "hour": "03",
        "daymonth": "*",
        "dayweek": "*",
        "month": "*",
        "attributes": {
            "bucket": os.environ['BACKUP_AWS_BUCKET'],
            "folder": "",
            "region": os.environ['BACKUP_AWS_REGION'],
        },
    }])
    assert req.status_code == 200
    creds['backupid'] = req.json()
    assert isinstance(creds['backupid'], int) is True


def test_backup_020_update(conn, creds):
    _check()
    req = conn.rest.put(f'backup/id/{creds["backupid"]}', data=[{
        "description": "backup_test"
    }])
    assert req.status_code == 200, req.text


def test_backup_050_sync(conn, creds):
    _check()
    rv = conn.ws.call('backup.sync', creds['backupid'], job=True)
    assert rv is True


def test_backup_800_delete(conn, creds):
    _check()
    req = conn.rest.delete(f'backup/id/{creds["backupid"]}')
    assert req.status_code == 200


def test_backup_900_credential_delete(conn, creds):
    _check()
    req = conn.rest.delete(f'backup/credential/id/{creds["credid"]}')
    assert req.status_code == 200
