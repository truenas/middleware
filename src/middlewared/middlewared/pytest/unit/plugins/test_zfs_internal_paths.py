import pytest

from middlewared.plugins.container.utils import CONTAINER_DS_NAME
from middlewared.plugins.zfs.utils import INTERNAL_PATHS, has_internal_path


def test_container_dataset_name_is_internal():
    # INTERNAL_PATHS spells the container dataset name out rather than importing it, so that the
    # zfs layer does not depend on a plugin package. This keeps the two from drifting apart.
    assert CONTAINER_DS_NAME in INTERNAL_PATHS


@pytest.mark.parametrize(
    "path",
    [
        "tank/.truenas_containers",
        "tank/.truenas_containers/containers",
        "tank/.truenas_containers/containers/foo",
        "tank/.truenas_containers/images/ubuntu:24.04",
    ],
)
def test_container_paths_are_internal(path):
    assert has_internal_path(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "tank",
        "tank/.truenas_containers_backup",
        "tank/data/.truenas_containers",
        # Legacy incus datasets are the source the container migration renames *from*, so they have to
        # stay outside the guard.
        "tank/.ix-virt/containers/foo",
    ],
)
def test_lookalike_paths_are_not_internal(path):
    assert has_internal_path(path) is False
