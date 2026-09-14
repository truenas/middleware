import base64
import contextlib
import io
import json
import os
import sqlite3
import tarfile
import tempfile

import pytest

from truenas_api_client import ClientException
from middlewared.test.integration.utils import call, session, ssh, url

NO_SEED = "does not include the password secret seed"
SEED_MISMATCH = "is not the one that encrypted its database"
INVALID_DB = "Uploaded TrueNAS database file is not valid"


@pytest.fixture(scope="module")
def this_system_seed():
    return base64.b64decode(ssh("base64 -w0 /data/pwenc_secret"))


@pytest.fixture(scope="module")
def this_system_pwenc_check():
    return call("datastore.config", "system.settings")["stg_pwenc_check"]


def make_db(pwenc_check=None, settings_table=True):
    """A real sqlite database carrying an alembic revision that cannot be migrated."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = os.path.join(tmp_dir, "freenas-v1.db")
        with contextlib.closing(sqlite3.connect(path)) as conn:
            with conn:
                conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);")
                conn.execute("INSERT INTO alembic_version VALUES ('invalid')")
                if settings_table:
                    conn.execute("CREATE TABLE system_settings (id INTEGER PRIMARY KEY, stg_pwenc_check BLOB);")
                    conn.execute("INSERT INTO system_settings VALUES (1, ?)", (pwenc_check,))

        with open(path, "rb") as f:
            return f.read()


def make_tar(members):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

    return buf.getvalue()


def upload_error(payload):
    with session() as s:
        r = s.post(
            f"{url()}/_upload",
            files={
                "data": (None, io.StringIO(json.dumps({
                    "method": "config.upload",
                    "params": [],
                }))),
                "file": (None, io.BytesIO(payload)),
            },
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]

    with pytest.raises(ClientException) as ve:
        call("core.job_wait", job_id, job=True)

    return ve.value.error


def test_invalid_database_file(this_system_seed, this_system_pwenc_check):
    """A matching seed and database pass validation, so the upload reaches the migration and fails there."""
    error = upload_error(make_tar({
        "freenas-v1.db": make_db(this_system_pwenc_check),
        "pwenc_secret": this_system_seed,
    }))

    assert INVALID_DB in error
    assert "Can't locate revision identified by 'invalid'" in error


@pytest.mark.parametrize("payload", [
    pytest.param(make_db(), id="bare_database"),
    pytest.param(make_tar({"freenas-v1.db": make_db()}), id="archive_without_seed"),
])
def test_upload_without_secret_seed_is_rejected(payload):
    assert NO_SEED in upload_error(payload)


def test_upload_with_wrong_secret_seed_is_rejected(this_system_pwenc_check):
    payload = make_tar({
        "freenas-v1.db": make_db(this_system_pwenc_check),
        "pwenc_secret": os.urandom(32),
    })

    assert SEED_MISMATCH in upload_error(payload)


@pytest.mark.parametrize("db_kwargs", [
    pytest.param({"pwenc_check": None}, id="null"),
    pytest.param({"pwenc_check": ""}, id="empty"),
    pytest.param({"pwenc_check": b"\x00" * 16}, id="blob"),
    pytest.param({"settings_table": False}, id="no_settings_table"),
])
def test_upload_with_unusable_check_value_is_rejected(this_system_seed, db_kwargs):
    payload = make_tar({"freenas-v1.db": make_db(**db_kwargs), "pwenc_secret": this_system_seed})

    assert INVALID_DB in upload_error(payload)
