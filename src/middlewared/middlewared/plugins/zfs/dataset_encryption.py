from typing import Any, Iterable, Sequence, TypedDict, TYPE_CHECKING

import truenas_pylibzfs
from truenas_pylibzfs import ZFSException
from middlewared.service import CallError

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


class EncryptionProperties(TypedDict, total=False):
    keyformat: Any
    keylocation: str
    pbkdf2iters: Any


def load_key(
    ctx: 'ServiceContext', id_: str, *,
    mount_ds: bool = True,
    recursive: bool = False,
    key: str | bytes | None = None,
    key_location: str | bytes | None = None
) -> None:
    try:
        lz = truenas_pylibzfs.open_handle()
        rsrc = lz.open_resource(name=id_)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{id_} is not encrypted')
        if crypto.info().key_is_loaded:
            raise CallError(f'{id_} key is already loaded')
        crypto.load_key(key=key, key_location=key_location)
    except ZFSException as e:
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
        lz = truenas_pylibzfs.open_handle()
        rsrc = lz.open_resource(name=id_)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{id_} is not encrypted')
        return crypto.check_key(key=key, key_location=key_location)
    except ZFSException as e:
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
        lz = truenas_pylibzfs.open_handle()
        rsrc = lz.open_resource(name=id_)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{id_} is not encrypted')
        config = lz.resource_cryptography_config(**(properties or {}), key=key)
        crypto.change_key(info=config)
        if load_key:
            crypto.load_key()
    except ZFSException as e:
        ctx.logger.error(f'Failed to change key for {id_}', exc_info=True)
        raise CallError(f'Failed to change key for {id_}: {e}')


def change_encryption_root(id_: str, load_key: bool = True) -> None:
    try:
        lz = truenas_pylibzfs.open_handle()
        rsrc = lz.open_resource(name=id_)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{id_} is not encrypted')
        crypto.inherit_key()
        if load_key:
            crypto.load_key()
    except ZFSException as e:
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
