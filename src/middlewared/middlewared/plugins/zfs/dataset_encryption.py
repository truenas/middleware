from typing import Any, Callable, Iterable, ParamSpec, Sequence, TypedDict, TYPE_CHECKING

import libzfs
from middlewared.service import CallError
if TYPE_CHECKING:
    from middlewared.service import ServiceContext


P = ParamSpec('P')


class EncryptionProperties(TypedDict, total=False):
    keyformat: Any
    keylocation: str
    pbkdf2iters: Any


def _common_encryption_checks(id_: str, ds: libzfs.ZFSDataset):
    if not ds.encrypted:
        raise CallError(f'{id_} is not encrypted')


def load_key(
    ctx: 'ServiceContext', id_: str, *,
    mount_ds: bool = True,
    recursive: bool = False,
    key: str | bytes | None = None,
    key_location: str | bytes | None = None
) -> None:
    try:
        with libzfs.ZFS() as zfs:
            ds = zfs.get_dataset(id_)
            _common_encryption_checks(id_, ds)
            if ds.key_loaded:
                raise CallError(f'{id_} key is already loaded')
            ds.load_key(key=key, key_location=key_location)
    except libzfs.ZFSException as e:
        ctx.logger.error(f'Failed to load key for {id_}', exc_info=True)
        raise CallError(f'Failed to load key for {id_}: {e}')
    else:
        if mount_ds:
            ctx.call_sync2(ctx.s.zfs.resource.mount, id_, recursive=recursive)


def check_key(
    ctx: 'ServiceContext',
    id_: str,
    key: str | bytes | None = None,
    key_location: str | bytes | None = None
) -> bool:
    try:
        with libzfs.ZFS() as zfs:
            ds = zfs.get_dataset(id_)
            _common_encryption_checks(id_, ds)
            return ds.check_key(key, key_location)
    except libzfs.ZFSException as e:
        ctx.logger.error(f'Failed to check key for {id_}', exc_info=True)
        raise CallError(f'Failed to check key for {id_}: {e}')


def change_key(
    ctx: 'ServiceContext',
    id_: str,
    properties: EncryptionProperties | None = None,
    load_key: bool = True,
    key: str | bytes | None = None
) -> None:
    try:
        with libzfs.ZFS() as zfs:
            ds = zfs.get_dataset(id_)
            _common_encryption_checks(id_, ds)
            ds.change_key(props=properties, load_key=load_key, key=key)
    except libzfs.ZFSException as e:
        ctx.logger.error(f'Failed to change key for {id_}', exc_info=True)
        raise CallError(f'Failed to change key for {id_}: {e}')


def change_encryption_root(id_: str, load_key: bool = True) -> None:
    try:
        with libzfs.ZFS() as zfs:
            ds = zfs.get_dataset(id_)
            ds.change_key(load_key=load_key, inherit=True)
    except libzfs.ZFSException as e:
        raise CallError(f'Failed to change encryption root for {id_}: {e}')


def bulk_check(ctx: 'ServiceContext', params: Iterable[Sequence]) -> list[dict]:
    statuses = []
    for i in params:
        result = error = None
        try:
            result = check_key(ctx, *i)
        except Exception as e:
            error = str(e)
        finally:
            statuses.append({'result': result, 'error': error})

    return statuses
