import io
import json
import subprocess
import tempfile

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.utils import call, session, url


def test_invalid_database_file():
    with tempfile.TemporaryDirectory() as td:
        subprocess.check_call([
            "sqlite3",
            "freenas-v1.db",
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL); "
            "INSERT INTO alembic_version VALUES ('invalid')"
        ], cwd=td)
        subprocess.check_call(["tar", "-cf", "config.tar", "freenas-v1.db"], cwd=td)

        with session() as s:
            r = s.post(
                f"{url()}/_upload",
                files={
                    "data": (None, io.StringIO(json.dumps({
                        "method": "config.upload",
                        "params": [],
                    }))),
                    "file": (None, open(f"{td}/config.tar", "rb")),
                },
            )
            r.raise_for_status()
            job_id = r.json()["job_id"]

        with pytest.raises(ClientException) as ve:
            call("core.job_wait", job_id, job=True)

        assert 'Uploaded TrueNAS database file is not valid' in ve.value.error
        assert "Can't locate revision identified by 'invalid'" in ve.value.error
