import os

from middlewared.utils import MIDDLEWARE_RUN_DIR

COMMUNITY_TRAIN = 'community'
IX_APP_NAME = 'ix-app'
OFFICIAL_ENTERPRISE_TRAIN = 'enterprise'
OFFICIAL_LABEL = 'TRUENAS'
OFFICIAL_CATALOG_REPO = 'https://github.com/truenas/apps'
OFFICIAL_CATALOG_BRANCH = 'master'
TMP_IX_APPS_CATALOGS = os.path.join(MIDDLEWARE_RUN_DIR, 'ix-apps/catalogs')


def get_cache_key(label: str, location: str) -> str:
    # The catalog location flips between the apps dataset and a tmpfs path depending on whether the
    # dataset is mounted, so it has to be part of the key - otherwise data written against one
    # location is served back for the other.
    return f'catalog_{label}_{location}_train_details'
