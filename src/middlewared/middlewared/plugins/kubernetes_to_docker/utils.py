import os


def get_sorted_backups(backups_config: dict) -> list:
    """
    Returns a list of backups sorted by their creation date with latest backups at the end of the list.
    """
    if backups_config['error'] or not backups_config['backups']:
        return []

    return sorted(
        [backup for backup in backups_config['backups'].values() if backup['releases']],
        key=lambda backup: backup['created_on'],
    )


def get_k8s_ds(pool_name: str) -> str:
    return os.path.join(pool_name, 'ix-applications')
