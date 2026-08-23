import pytest

from middlewared.plugins.apps.ix_apps.path import (
    get_app_parent_volume_path,
    get_app_volume_path,
    is_app_mounts_path,
    is_app_volume_path,
)


@pytest.mark.parametrize(
    "path, app_name, should_match",
    [
        (get_app_volume_path("plex"), "plex", True),
        (f"{get_app_volume_path('plex')}/data", "plex", True),
        (f"{get_app_volume_path('plex')}/data/nested/deeper", "plex", True),
        (f"{get_app_volume_path('plex')}/", "plex", True),
        (f"{get_app_volume_path('plex')}//data", "plex", True),
        (f"{get_app_volume_path('plex')}/data/../config", "plex", True),
        (get_app_volume_path("sonarr"), "plex", False),
        # These share a name prefix with the app but are separate directories
        (get_app_volume_path("plex-extra"), "plex", False),
        (f"{get_app_volume_path('plex2')}/data", "plex", False),
        # Traversal out of the volume directory has to be caught even though nothing is resolved on disk
        (f"{get_app_volume_path('plex')}/../sonarr/data", "plex", False),
        (f"{get_app_volume_path('plex')}/../../../../mnt/tank/data", "plex", False),
        ("/mnt/tank/data", "plex", False),
        ("", "plex", False),
        ("data", "plex", False),
    ],
)
def test_is_app_volume_path(path, app_name, should_match):
    assert is_app_volume_path(path, app_name) is should_match


@pytest.mark.parametrize(
    "path, should_match",
    [
        (get_app_parent_volume_path(), True),
        (f"{get_app_parent_volume_path()}/", True),
        # Any app's volume directory is under the shared root, no app identity involved
        (get_app_volume_path("plex"), True),
        (f"{get_app_volume_path('plex')}/data/nested/deeper", True),
        (get_app_volume_path("sonarr"), True),
        (f"{get_app_parent_volume_path()}//plex", True),
        (f"{get_app_volume_path('plex')}/data/../config", True),
        # A sibling directory sharing the root's name prefix is not inside it
        (f"{get_app_parent_volume_path()}-old/plex", False),
        # Traversal out of the root has to be caught even though nothing is resolved on disk
        (f"{get_app_volume_path('plex')}/../../../../mnt/tank/data", False),
        (f"{get_app_parent_volume_path()}/../app_configs/plex", False),
        ("/mnt/.ix-apps/app_configs/plex", False),
        ("/mnt/tank/data", False),
        ("", False),
        ("data", False),
    ],
)
def test_is_app_mounts_path(path, should_match):
    assert is_app_mounts_path(path) is should_match
