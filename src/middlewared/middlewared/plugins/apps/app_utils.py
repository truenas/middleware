from collections import namedtuple


app_details = namedtuple('app_details', ['name', 'version'])


def get_app_details_from_version_path(version_path: str) -> app_details:
    version_path = version_path.split('/')
    return app_details(name=version_path[-3], version=version_path[-1])
