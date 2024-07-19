import os


def get_backup_dir(k8s_ds: str) -> str:
    return os.path.join('/mnt', k8s_ds, 'backups')
