import textwrap

import pytest

from middlewared.plugins.pool import parse_lsof


@pytest.mark.parametrize("lsof,dirs,result", [
    (
        textwrap.dedent("""\
            p535
            cpython3.7
            f5
            n/usr/lib/data
            p536
            cpython3.7
            f5
            n/dev/zvol/backup/vol1
            p537
            cpython3.7
            f5
            n/dev/zvol/tank/vols/vol1
            p2520
            csmbd
            f9
            n/mnt/tank/blob1
            f31
            n/mnt/backup/blob2
            p97778
            cminio
            f7
            n/mnt/tank/data/blob3
        """),
        ["/mnt/tank", "/dev/zvol/tank"],
        [
            (537, "python3.7"),
            (2520, "smbd"),
            (97778, "minio"),
        ]
    )
])
def test__parse_lsof(lsof, dirs, result):
    assert parse_lsof(lsof, dirs) == result
