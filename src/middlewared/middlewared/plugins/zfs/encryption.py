import threading
from typing import Literal, TypedDict, TYPE_CHECKING, cast

from truenas_pylibzfs import ZFSException
from middlewared.service import CallError

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


class EncryptionProperties(TypedDict, total=False):
    keyformat: Literal['hex', 'passphrase', 'raw']
    keylocation: str
    pbkdf2iters: int | None


def load_key(ctx: 'ServiceContext', tls: threading.local, dataset: str, **kwargs) -> None:
    """Load the encryption key for `dataset`.

    Raises CallError if the dataset is not encrypted, the key is already
    loaded, or the ZFS operation fails.

    `key` (str | bytes) and `key_location` (str) are mutually exclusive.
    Pass `key` as str for hex/passphrase keyformats or as bytes for raw
    keyformat. Key material is passed to ZFS via an in-memory file and
    never written to disk.
    """
    if len(kwargs) > 1:
        raise ValueError('Cannot specify both key and key location')
    try:
        rsrc = tls.lzh.open_resource(name=dataset)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{dataset} is not encrypted')
        if crypto.info().key_is_loaded:
            raise CallError(f'{dataset} key is already loaded')
        crypto.load_key(**kwargs)
    except (ZFSException, ValueError) as e:
        ctx.logger.error(f'Failed to load key for {dataset}', exc_info=True)
        raise CallError(f'Failed to load key for {dataset}: {e}')


def check_key(ctx: 'ServiceContext', tls: threading.local, dataset: str, **kwargs) -> bool:
    """Return True if `key` (or the key at `key_location`) can unlock `dataset`.

    Does not actually load the key. Raises CallError if the dataset is not
    encrypted or if the ZFS operation fails for a reason other than a wrong
    key (EZFS_CRYPTOFAILED returns False rather than raising).

    `key` (str | bytes) and `key_location` (str) are mutually exclusive.
    Pass `key` as str for hex/passphrase keyformats or as bytes for raw
    keyformat.
    """
    if len(kwargs) > 1:
        raise ValueError('Cannot specify both key and key location')
    try:
        rsrc = tls.lzh.open_resource(name=dataset)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{dataset} is not encrypted')
        return crypto.check_key(**kwargs)
    except (ZFSException, ValueError) as e:
        ctx.logger.error(f'Failed to check key for {dataset}', exc_info=True)
        raise CallError(f'Failed to check key for {dataset}: {e}')


def change_key(
    ctx: 'ServiceContext',
    tls: threading.local,
    dataset: str,
    properties: EncryptionProperties | None = None,
    key: str | None = None
) -> None:
    """Change the encryption key and/or properties for `dataset`.

    `properties` may contain any combination of keyformat, keylocation, and
    pbkdf2iters. `key` is the new key material and is required when
    keylocation is not given. The dataset's key must already be loaded before
    calling this. Raises CallError on failure.
    """
    props = {} if properties is None else cast(dict, properties.copy())
    if key:
        props.pop('keylocation', None)
        props['key'] = key
    elif 'keylocation' not in props:
        raise ValueError('Must specify either key or key location')

    try:
        rsrc = tls.lzh.open_resource(name=dataset)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{dataset} is not encrypted')
        config = tls.lzh.resource_cryptography_config(**props)
        crypto.change_key(info=config)
    except (ZFSException, ValueError) as e:
        ctx.logger.error(f'Failed to change key for {dataset}', exc_info=True)
        raise CallError(f'Failed to change key for {dataset}: {e}')


def change_encryption_root(tls: threading.local, dataset: str) -> None:
    """Make `dataset` inherit encryption from its parent, removing it as
    an encryption root.

    `dataset` must currently be an encryption root and its key must be loaded.
    Raises CallError on failure.
    """
    try:
        rsrc = tls.lzh.open_resource(name=dataset)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{dataset} is not encrypted')
        crypto.inherit_key()
    except (ZFSException, ValueError) as e:
        raise CallError(f'Failed to change encryption root for {dataset}: {e}')
