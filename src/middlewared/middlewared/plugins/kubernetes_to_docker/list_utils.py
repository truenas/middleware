import os


K8s_BACKUP_NAME_PREFIX = 'ix-applications-backup-'


def get_backup_dir(k8s_ds: str) -> str:
    return os.path.join('/mnt', k8s_ds, 'backups')
