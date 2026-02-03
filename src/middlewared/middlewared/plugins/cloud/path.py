import os
import stat

from middlewared.service import CallError


def get_remote_path(provider, attributes):
    remote_path = attributes["folder"].rstrip("/")
    if not remote_path:
        remote_path = "/"
    if provider.buckets:
        remote_path = f"{attributes['bucket']}/{remote_path.lstrip('/')}"
    return remote_path


def check_local_path(middleware, path, *, check_mountpoint=True, error_text_path=None):
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
