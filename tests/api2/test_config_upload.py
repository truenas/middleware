import contextlib
import io
import json
import sqlite3
import tarfile
import os

import pytest

from truenas_api_client import ClientException
from middlewared.test.integration.utils import call, session, url

MIGRATION_FAILED = "Uploaded TrueNAS database file could not be migrated"
NOT_SQLITE = "Uploaded TrueNAS database file is not a SQLite database"


@contextlib.contextmanager
def db_ops(db_name):
    try:
        with contextlib.closing(sqlite3.connect(db_name)) as conn:
            with conn:
                conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);")
                conn.execute("INSERT INTO alembic_version VALUES ('invalid')")
            yield
    finally:
        os.unlink(db_name)


@contextlib.contextmanager
def tar_ops(file_to_add):
    tar_name = "config.tar"
    tfile = None
    try:
        with tarfile.open(tar_name, "w") as tfile:
            tfile.add(file_to_add)
        yield tfile.name
    finally:
        if tfile is not None:
            os.unlink(tfile.name)


def upload_error(fileobj):
    with session() as s:
        r = s.post(
            f"{url()}/_upload",
            files={
                "data": (None, io.StringIO(json.dumps({
                    "method": "config.upload",
                    "params": [],
                }))),
                "file": (None, fileobj),
            },
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]

    with pytest.raises(ClientException) as ve:
        call("core.job_wait", job_id, job=True)

    return ve.value.error


def test_invalid_database_file():
    db_name = "freenas-v1.db"
    with db_ops(db_name):
        with tar_ops(db_name) as tar_name:
            with open(tar_name, "rb") as f:
                error = upload_error(f)

    assert MIGRATION_FAILED in error
    assert "Traceback" not in error


def test_upload_of_non_sqlite_database_is_rejected():
    error = upload_error(io.BytesIO(b"not a database"))

    assert NOT_SQLITE in error
    assert "Traceback" not in error
