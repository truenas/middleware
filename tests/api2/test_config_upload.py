import contextlib
import io
import json
import sqlite3
import tarfile
import os

import pytest

from truenas_api_client import ClientException
from middlewared.test.integration.utils import call, session, url


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


def test_invalid_database_file():
    db_name = "freenas-v1.db"
    with db_ops(db_name):
        with tar_ops(db_name) as tar_name:
            with session() as s:
                r = s.post(
                    f"{url()}/_upload",
                    files={
                        "data": (None, io.StringIO(json.dumps({
                            "method": "config.upload",
                            "params": [],
                        }))),
                        "file": (None, open(tar_name, "rb")),
                    },
                )
                r.raise_for_status()
                job_id = r.json()["job_id"]
                with pytest.raises(ClientException) as ve:
                    call("core.job_wait", job_id, job=True)

                assert 'Uploaded TrueNAS database file is not valid' in ve.value.error
                assert "Can't locate revision identified by 'invalid'" in ve.value.error
