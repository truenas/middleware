import os


K8s_BACKUP_NAME_PREFIX = 'ix-applications-backup-'


def get_backup_dir(k8s_ds: str) -> str:
    return os.path.join('/mnt', k8s_ds, 'backups')


def chart_release_can_be_migrated(release_name: str, release_path: str, catalog_path: str, apps_mapping: dict) -> bool:
    return False
