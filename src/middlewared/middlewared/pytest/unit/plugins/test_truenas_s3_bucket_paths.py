import pytest

from middlewared.common.attachment import LocalPathWriter
from middlewared.plugins.truenas_s3.bucket_crud import reaches


def writer(path, crosses_mounts=True, dataset=None, relative_path=None):
    return LocalPathWriter(
        name="writer", path=path, dataset=dataset, relative_path=relative_path, crosses_mounts=crosses_mounts
    )


@pytest.mark.parametrize(
    "w, expected",
    [
        (writer("/mnt/tank/ab"), False),
        (writer("/mnt/tank"), True),
        (writer("/mnt/tank", crosses_mounts=False), False),
        (writer("/mnt/tank/a/s3data", crosses_mounts=False), True),
        (writer("/mnt/elsewhere", crosses_mounts=False, dataset="tank/a", relative_path="x"), True),
        # a directory the bucket's dataset mounts over
        (writer("/mnt/tank/a", crosses_mounts=False, dataset="tank", relative_path="a"), True),
    ],
)
def test_reaches(w, expected):
    assert reaches("tank/a", w) is expected
