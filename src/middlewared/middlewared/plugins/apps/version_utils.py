import errno

from packaging.version import Version

from middlewared.service import CallError


def get_latest_version_from_app_versions(app_versions: dict) -> str:
    if not app_versions:
        raise CallError('No versions found', errno=errno.ENOENT)
    elif all(not app_version['healthy'] for app_version in app_versions.values()):
        raise CallError('No healthy app version found', errno=errno.ENOENT)

    return str(sorted(map(Version, app_versions) or ['latest'], reverse=True)[0])
