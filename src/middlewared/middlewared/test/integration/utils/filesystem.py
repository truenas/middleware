import contextlib
import typing

from .call import call


__all__ = ['file_exists_and_perms_check']


def file_exists_and_perms_check(file_path: str, options: typing.Optional[dict] = None):
    options = options or {}
    options.setdefault('type', 'FILE')
    with contextlib.suppress(Exception):
        file_info = call('filesystem.stat', file_path)
        return all(file_info.get(k) == options[k] for k in options)

    return False
