import textwrap

import pytest

from middlewared.plugins.pool import parse_lsof


@pytest.mark.parametrize("lsof,result", [
    (
        textwrap.dedent("""\
            p2520
            csmbd
            f9
            f31
            p97778
            cminio
            f7
        """),
        [
            (2520, "smbd"),
            (97778, "minio"),
        ]
    )
])
def test__parse_lsof(lsof, result):
    assert parse_lsof(lsof) == result
