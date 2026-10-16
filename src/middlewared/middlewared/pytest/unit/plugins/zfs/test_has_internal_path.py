import pytest

from middlewared.plugins.container.utils import container_dataset
from middlewared.plugins.zfs.utils import has_internal_path


@pytest.mark.parametrize(
    "path,expected",
    [
        (f"{container_dataset('tank')}/x", True),
        ("tank/ix-applications/x", True),
        ("tank/ix-applications", False),
        ("tank/ix-apps-old", False),
        ("tank/x/.system", False),
    ],
)
def test_has_internal_path(path, expected):
    assert has_internal_path(path) is expected
