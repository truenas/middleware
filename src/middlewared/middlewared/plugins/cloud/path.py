from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

from middlewared.service import CallError

if TYPE_CHECKING:
    from middlewared.api.current import CloudTaskAttributes
    from middlewared.main import Middleware
    from middlewared.rclone.base import BaseRcloneRemote


def get_remote_path(provider: BaseRcloneRemote, attributes: CloudTaskAttributes) -> str:
    attrs = attributes.model_dump(by_alias=True)
    remote_path = attrs["folder"].rstrip("/")
    if not remote_path:
        remote_path = "/"
    if provider.buckets:
        remote_path = f"{attrs['bucket']}/{remote_path.lstrip('/')}"
    return remote_path


def check_local_path(
    middleware: Middleware,
    path: str,
    *,
    check_mountpoint: bool = True,
    error_text_path: str | None = None,
) -> None:
    error_text_path = error_text_path or path

    try:
        info = os.stat(path)
    except FileNotFoundError:
        raise CallError(f"Directory {error_text_path!r} does not exist")
    else:
        if not stat.S_ISDIR(info.st_mode):
            raise CallError(f"{error_text_path!r} is not a directory")

    if check_mountpoint:
        if not middleware.call_sync("filesystem.is_dataset_path", path):
            raise CallError(f"Directory {error_text_path!r} must reside within volume mount point")
