from typing import Literal

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass


__all__ = [
    'WebShareEntry', 'WebShareUpdateArgs', 'WebShareUpdateResult',
    'WebShareValidateArgs', 'WebShareValidateResult'
]


class WebShareEntry(BaseModel):
    id: int
    truenas_host: str = "localhost"
    """Host to connect to TrueNAS API for authentication."""
    log_level: Literal['debug', 'info', 'warn', 'error'] = "info"
    """Logging level for WebShare services."""
    session_log_retention: int = 20
    """Number of days to retain session logs."""
    enable_web_terminal: bool = False
    """Enable web-based terminal feature."""
    bulk_download_pool: str | None = None
    """Pool name for bulk download temporary storage. Must be a valid imported pool."""
    search_index_pool: str | None = None
    """Pool name for search index storage. Must be a valid imported pool."""
    altroots: dict[str, str]
    """Alternative root paths for file system access. Keys and values must be unique.
    Values must be paths under /mnt/<poolname>."""
    altroots_metadata: dict[str, dict[str, bool]] = {}
    """Metadata for alternative roots. Keys match altroots keys. 
    Each value is a dict containing metadata like {'search_indexed': bool}."""
    search_enabled: bool = False
    """Enable file search and indexing functionality."""
    search_directories: list[str]
    """List of directories to index for search. Must be paths under /mnt/<poolname>."""
    search_max_file_size: int = 104857600
    """Maximum file size to index in bytes (default: 100MB)."""
    search_supported_types: list[Literal[
        'image', 'audio', 'video', 'document', 'archive', 'text', 'disk_image'
    ]]
    """File types to include in search index."""
    search_worker_count: int = 4
    """Number of parallel workers for indexing."""
    search_archive_enabled: bool = True
    """Enable indexing of files within archives."""
    search_archive_max_depth: int = 2
    """Maximum depth to recurse into nested archives."""
    search_archive_max_size: int = 524288000
    """Maximum archive size to process in bytes (default: 500MB)."""
    search_index_max_size: int = 10737418240
    """Maximum search index size in bytes (default: 10GB)."""
    search_index_cleanup_enabled: bool = True
    """Enable automatic cleanup when index is full."""
    search_index_cleanup_threshold: int = 90
    """Cleanup threshold as percentage of max size (0-100)."""
    search_pruning_enabled: bool = False
    """Enable periodic pruning of deleted files from index."""
    search_pruning_schedule: Literal['hourly', 'daily', 'weekly'] = 'daily'
    """Schedule for index pruning."""
    search_pruning_start_time: str = "23:00"
    """Time to start pruning in HH:MM format."""


class WebShareUpdate(WebShareEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class WebShareUpdateArgs(BaseModel):
    data: WebShareUpdate


class WebShareUpdateResult(BaseModel):
    result: WebShareEntry


class WebShareValidateArgs(BaseModel):
    data: WebShareUpdate


class WebShareValidateResult(BaseModel):
    result: None
