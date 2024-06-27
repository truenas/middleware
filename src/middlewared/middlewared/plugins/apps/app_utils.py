from collections import namedtuple
from pathlib import Path

from semantic_version import Version

from .app_path_utils import get_installed_app_versions_dir_path


app_details = namedtuple('app_details', ['name', 'version'])


def get_app_details_from_version_path(version_path: str) -> app_details:
    version_path = version_path.split('/')
    return app_details(name=version_path[-3], version=version_path[-1])


def get_version_in_use_of_app(app_name: str) -> str:
    # Raises an Index error if no versions are found
    # This will treat the latest version available as the current one which is being used
    versions_path = Path(get_installed_app_versions_dir_path(app_name))
    return sorted([Version(v.name) for v in versions_path.iterdir() if v.is_dir()])[-1].__str__()
