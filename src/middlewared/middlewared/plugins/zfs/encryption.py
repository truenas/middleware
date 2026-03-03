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
    """
    Load the encryption key for a ZFS dataset.

    Args:
        dataset: Name of the ZFS dataset whose key should be loaded.

    Keyword Args:
        key: Key material as ``str`` (hex/passphrase) or ``bytes`` (raw).
            Mutually exclusive with ``key_location``.
        key_location: Path to the key file on disk.
            Mutually exclusive with ``key``.
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
    """
    Return True if ``key`` (or the key at ``key_location``) can unlock ``dataset``.

    Does not actually load the key. Raises CallError if the dataset is not
    encrypted or if the ZFS operation fails for a reason other than a wrong
    key (EZFS_CRYPTOFAILED returns False rather than raising).

    Args:
        dataset: Name of the ZFS dataset to check.

    Keyword Args:
        key: Key material as ``str`` (hex/passphrase) or ``bytes`` (raw).
            Mutually exclusive with ``key_location``.
        key_location: Path to the key file on disk.
            Mutually exclusive with ``key``.
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
    """
    Change the encryption key and/or properties for ``dataset``.

    The dataset's key must already be loaded before calling this.
    Raises CallError on failure.

    Args:
        dataset: Name of the ZFS dataset whose key should be changed.
        properties: May contain any combination of keyformat, keylocation, and
            pbkdf2iters.
        key: New key material. Required when keylocation is not given.
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
    """
    Make ``dataset`` inherit encryption from its parent, removing it as
    an encryption root.

    ``dataset`` must currently be an encryption root and its key must be loaded.
    Raises CallError on failure.

    Args:
        dataset: Name of the ZFS dataset to remove as an encryption root.
    """
    try:
        rsrc = tls.lzh.open_resource(name=dataset)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{dataset} is not encrypted')
        crypto.inherit_key()
    except (ZFSException, ValueError) as e:
        raise CallError(f'Failed to change encryption root for {dataset}: {e}')
