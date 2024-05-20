import os

from middlewared.utils import MIDDLEWARE_RUN_DIR


OFFICIAL_ENTERPRISE_TRAIN = 'enterprise'
OFFICIAL_LABEL = 'TRUENAS'
TMP_IX_APPS_CATALOGS = os.path.join(MIDDLEWARE_RUN_DIR, 'ix-apps/catalogs')


def get_cache_key(label: str) -> str:
    return f'catalog_{label}_train_details'
