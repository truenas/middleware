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
    key: str | None = None,
    key_location: str | None = None
) -> None:
    """Load the encryption key for dataset `id_`.

    Raises CallError if the dataset is not encrypted, the key is already
    loaded, or the ZFS operation fails. On success, mounts the dataset
    (and optionally its children) unless `mount_ds` is False.

    `key` and `key_location` are mutually exclusive. Key material is passed
    to ZFS via an in-memory file and never written to disk.
    """
    try:
        lz = truenas_pylibzfs.open_handle()
        rsrc = lz.open_resource(name=id_)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{id_} is not encrypted')
        if crypto.info().key_is_loaded:
            raise CallError(f'{id_} key is already loaded')
        crypto.load_key(key=key, key_location=key_location)
    except (ZFSException, ValueError) as e:
        ctx.logger.error(f'Failed to load key for {id_}', exc_info=True)
        raise CallError(f'Failed to load key for {id_}: {e}')
    else:
        if mount_ds:
            ctx.call_sync2(ctx.s.zfs.resource.mount, id_, recursive=recursive)


def check_key(
    ctx: 'ServiceContext',
    id_: str,
    key: str | None = None,
    key_location: str | None = None
) -> bool:
    """Return True if `key` (or the key at `key_location`) can unlock `id_`.

    Does not actually load the key. Raises CallError if the dataset is not
    encrypted or if the ZFS operation fails for a reason other than a wrong
    key (EZFS_CRYPTOFAILED returns False rather than raising).
    """
    try:
        lz = truenas_pylibzfs.open_handle()
        rsrc = lz.open_resource(name=id_)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{id_} is not encrypted')
        return crypto.check_key(key=key, key_location=key_location)
    except (ZFSException, ValueError) as e:
        ctx.logger.error(f'Failed to check key for {id_}', exc_info=True)
        raise CallError(f'Failed to check key for {id_}: {e}')


def change_key(
    ctx: 'ServiceContext',
    id_: str,
    properties: EncryptionProperties | None = None,
    load_key: bool = True,
    key: str | None = None
) -> None:
    """Change the encryption key and/or properties for dataset `id_`.

    `properties` may contain any combination of keyformat, keylocation, and
    pbkdf2iters. `key` is the new key material and is required when
    keylocation is 'prompt'. The dataset's key must already be loaded before
    calling this. If `load_key` is True, the new key is loaded immediately
    after the change. Raises CallError on failure.
    """
    try:
        lz = truenas_pylibzfs.open_handle()
        rsrc = lz.open_resource(name=id_)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{id_} is not encrypted')
        config = lz.resource_cryptography_config(**(properties or {}), key=key)
        crypto.change_key(info=config)
        if load_key:
            crypto.load_key()
    except (ZFSException, ValueError) as e:
        ctx.logger.error(f'Failed to change key for {id_}', exc_info=True)
        raise CallError(f'Failed to change key for {id_}: {e}')


def change_encryption_root(id_: str, load_key: bool = True) -> None:
    """Make dataset `id_` inherit encryption from its parent, removing it as
    an encryption root.

    `id_` must currently be an encryption root and its key must be loaded.
    If `load_key` is True, the inherited key is loaded after the change.
    Raises CallError on failure.
    """
    try:
        lz = truenas_pylibzfs.open_handle()
        rsrc = lz.open_resource(name=id_)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{id_} is not encrypted')
        crypto.inherit_key()
        if load_key:
            crypto.load_key()
    except (ZFSException, ValueError) as e:
        raise CallError(f'Failed to change encryption root for {id_}: {e}')


def bulk_check(ctx: 'ServiceContext', params: Iterable[Sequence]) -> list[dict]:
    """Run check_key for each parameter list in `params`.

    Returns a list of dicts in the same order as `params`, each with keys:
      - 'result': True/False from check_key, or None if an exception occurred
      - 'error': str(exception) if one was raised, otherwise None
    """
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
