import os

from middlewared.utils import MIDDLEWARE_RUN_DIR


OFFICIAL_ENTERPRISE_TRAIN = 'enterprise'
OFFICIAL_LABEL = 'TRUENAS'
TMP_IX_APPS_CATALOGS = os.path.join(MIDDLEWARE_RUN_DIR, 'ix-apps/catalogs')


def convert_repository_to_path(git_repository_uri: str, branch: str) -> str:
    return git_repository_uri.split('://', 1)[-1].replace('/', '_').replace('.', '_') + f'_{branch}'
