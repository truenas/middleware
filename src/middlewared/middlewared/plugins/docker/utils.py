import os


BACKUP_NAME_PREFIX = 'ix-apps-backup-'
MIGRATION_NAMING_SCHEMA = 'ix-apps-migrate-%Y-%m-%d_%H-%M'
UPDATE_BACKUP_PREFIX = 'system-update-'


def applications_ds_name(pool: str) -> str:
    return os.path.join(pool, 'ix-apps')
