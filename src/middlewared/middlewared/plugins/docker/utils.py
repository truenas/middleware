import os


def applications_ds_name(pool: str) -> str:
    return os.path.join(pool, 'ix-apps')
