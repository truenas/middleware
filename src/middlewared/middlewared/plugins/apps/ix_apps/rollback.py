import os

from pkg_resources import parse_version

from .path import get_installed_app_versions_dir_path
from .utils import RE_VERSION


def get_rollback_versions(app_name: str, current_version: str) -> list[str]:
    rollback_versions = []
    with os.scandir(get_installed_app_versions_dir_path(app_name)) as scan:
        for entry in filter(
            lambda e: e.name != current_version and e.is_dir() and RE_VERSION.findall(e.name), scan
        ):
            rollback_versions.append(entry.name)

    return sorted(rollback_versions, key=parse_version)
