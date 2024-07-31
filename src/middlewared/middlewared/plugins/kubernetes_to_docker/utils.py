import os


def get_k8s_ds(pool_name: str) -> str:
    return os.path.join(pool_name, 'ix-applications')
