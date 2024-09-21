import os


IX_APPS_DIR_NAME = '.ix-apps'
IX_APPS_MOUNT_PATH: str = os.path.join('/mnt', IX_APPS_DIR_NAME)

DOCKER_DATASET_PROPS = {
    'aclmode': 'discard',
    'acltype': 'posix',
    'atime': 'off',
    'casesensitivity': 'sensitive',
    'canmount': 'noauto',
    'dedup': 'off',
    'encryption': 'off',
    'exec': 'on',
    'normalization': 'none',
    'overlay': 'on',
    'setuid': 'on',
    'snapdir': 'hidden',
    'xattr': 'sa',
}


def dataset_props(ds_name: str) -> dict:
    return DOCKER_DATASET_PROPS | {
        'mountpoint': IX_APPS_MOUNT_PATH if ds_name.endswith('/ix-apps') else os.path.join(
            IX_APPS_MOUNT_PATH, ds_name.split('/', 2)[-1]
        ),
    }
