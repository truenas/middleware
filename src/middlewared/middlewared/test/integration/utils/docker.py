import os


IX_APPS_DIR_NAME = '.ix-apps'
IX_APPS_MOUNT_PATH: str = os.path.join('/mnt', IX_APPS_DIR_NAME)
IX_APPS_CATALOG_PATH: str = os.path.join(IX_APPS_MOUNT_PATH, 'truenas_catalog')
