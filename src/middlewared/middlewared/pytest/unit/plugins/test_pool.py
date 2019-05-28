import textwrap

import pytest

from middlewared.plugins.pool import parse_lsof


@pytest.mark.parametrize("lsof,dir,result", [
    (
        textwrap.dedent("""\
            p535
            cpython3.7
            f5
            n/usr/lib/data
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
        "/mnt/tank",
        [
            (2520, "smbd"),
            (97778, "minio"),
        ]
    )
])
def test__parse_lsof(lsof, dir, result):
    assert parse_lsof(lsof, dir) == result
