from typing import Literal

from middlewared.api.base import (BaseModel, Excluded, ForUpdateMetaclass,
                                  excluded_field)

__all__ = [
    'WebShareEntry', 'WebShareUpdateArgs', 'WebShareUpdateResult',
    'WebShareValidateArgs', 'WebShareValidateResult', 'ShareConfig',
    'WebShareRemovePasskeyArgs', 'WebShareRemovePasskeyData',
    'WebShareRemovePasskeyResult'
]


class ShareConfig(BaseModel):
    name: str
    """Unique name for the share."""
    path: str
    """Filesystem path under /mnt/<poolname>/."""
    search_indexed: bool = True
    """Whether this share should be indexed for search."""
    is_home_base: bool = False
    """Whether this share is the base for user home directories."""


class WebShareEntry(BaseModel):
    id: int
    truenas_host: str = "localhost"
    """Host to connect to TrueNAS API for authentication."""
    log_level: Literal['debug', 'info', 'warn', 'error'] = "info"
    """Logging level for WebShare services."""
    pam_service_name: str = "webshare"
    """PAM service name for authentication (read-only, always 'webshare')."""
    allowed_groups: list[str] = ["webshare"]
    """List of groups allowed to access WebShare service."""
    session_log_retention: int = 20
    """Number of days to retain session logs."""
    enable_web_terminal: bool = False
    """Enable web-based terminal feature."""
    bulk_download_pool: str | None = None
    """Pool name for bulk download temporary storage. Must be a valid
    imported pool."""
    search_index_pool: str | None = None
    """Pool name for search index storage. Must be a valid imported pool."""
    shares: list[ShareConfig] = []
    """List of file share configurations. Each share has a unique name, path,
    and optional home base designation."""
    home_directory_template: str = "{{.Username}}"
    """Template for home directory names. Supports {{.Username}}, {{.UID}},
    and {{.GID}} placeholders."""
    home_directory_perms: str = "0700"
    """Permissions for newly created home directories in octal notation."""
    search_enabled: bool = False
    """Enable file search and indexing functionality."""
    search_directories: list[str]
    """List of directories to index for search. Must be paths under
    /mnt/<poolname>."""
    search_max_file_size: int = 104857600
    """Maximum file size to index in bytes (default: 100MB)."""
    search_supported_types: list[Literal[
        'image', 'audio', 'video', 'document', 'archive', 'text',
        'disk_image'
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
    proxy_port: int = 755
    """Port for the WebShare proxy service (1-65535)."""
    proxy_bind_addrs: list[str] = ["0.0.0.0"]
    """List of addresses to bind the proxy service to."""
    storage_admins: bool = False
    """Enable storage admin functionality in the file manager."""
    passkey_mode: Literal['disabled', 'enabled', 'required'] = 'disabled'
    """Passkey authentication mode: disabled, enabled, or required."""
    passkey_rp_origins: list[str] = []
    """List of allowed origins for WebAuthn relying party."""


class WebShareUpdate(WebShareEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    pam_service_name: Excluded = excluded_field()


class WebShareUpdateArgs(BaseModel):
    data: WebShareUpdate


class WebShareUpdateResult(BaseModel):
    result: WebShareEntry


class WebShareValidateArgs(BaseModel):
    data: WebShareUpdate


class WebShareValidateResult(BaseModel):
    result: None


class WebShareRemovePasskeyArgs(BaseModel):
    username: str


class WebShareRemovePasskeyData(BaseModel):
    username: str
    success: bool
    message: str
    output: str


class WebShareRemovePasskeyResult(BaseModel):
    result: WebShareRemovePasskeyData
