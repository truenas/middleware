from typing import Any

__all__ = (
    "DATASET_ENCRYPTION_EXPORT_KEYS_LOCK",
    "DATASET_ENCRYPTION_LOCK",
    "dataset_encryption_change_key_lock",
    "dataset_encryption_sync_keys_lock",
    "dataset_encryption_unlock_lock",
    "dataset_encryption_unlock_summary_lock",
)

DATASET_ENCRYPTION_LOCK = "dataset_encryption_lock"
DATASET_ENCRYPTION_EXPORT_KEYS_LOCK = "dataset_encryption_export_keys"


def dataset_encryption_unlock_lock(path: str) -> str:
    return f"dataset_encryption_unlock_{path}"


def dataset_encryption_unlock_summary_lock(path: str) -> str:
    return f"dataset_encryption_unlock_summary_{path}"


def dataset_encryption_change_key_lock(path: str) -> str:
    return f"dataset_encryption_change_key_{path}"


def dataset_encryption_sync_keys_lock(args: Any) -> str:
    return f"dataset_encryption_sync_keys_{args}"
