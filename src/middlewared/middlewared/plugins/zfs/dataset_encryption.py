import threading
from typing import Iterable, Literal, NotRequired, TypedDict, TYPE_CHECKING, cast

from truenas_pylibzfs import ZFSException
from middlewared.service import CallError

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


class EncryptionProperties(TypedDict, total=False):
    keyformat: Literal['hex', 'passphrase', 'raw']
    keylocation: str
    pbkdf2iters: int | None


class CheckKeyParams(TypedDict):
    id_: str
    key: NotRequired[str | bytes]
    key_location: NotRequired[str]


class CheckKeyResult(TypedDict):
    result: bool | None
    error: str | None


def load_key(ctx: 'ServiceContext', tls: threading.local, id_: str, **kwargs) -> None:
    if len(kwargs) > 1:
        raise ValueError('Cannot specify both key and key location')
    try:
        rsrc = tls.lzh.open_resource(name=id_)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{id_} is not encrypted')
        if crypto.info().key_is_loaded:
            raise CallError(f'{id_} key is already loaded')
        crypto.load_key(**kwargs)
    except (ZFSException, ValueError) as e:
        ctx.logger.error(f'Failed to load key for {id_}', exc_info=True)
        raise CallError(f'Failed to load key for {id_}: {e}')


def check_key(ctx: 'ServiceContext', tls: threading.local, id_: str, **kwargs) -> bool:
    """Return True if `key` (or the key at `key_location`) can unlock `id_`.

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
        rsrc = tls.lzh.open_resource(name=id_)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{id_} is not encrypted')
        return crypto.check_key(**kwargs)
    except (ZFSException, ValueError) as e:
        ctx.logger.error(f'Failed to check key for {id_}', exc_info=True)
        raise CallError(f'Failed to check key for {id_}: {e}')


def change_key(
    ctx: 'ServiceContext',
    tls: threading.local,
    id_: str,
    properties: EncryptionProperties | None = None,
    key: str | None = None
) -> None:
    props = {} if properties is None else cast(dict, properties.copy())
    if key:
        props.pop('keylocation', None)
        props['key'] = key
    elif 'keylocation' not in props:
        raise ValueError('Must specify either key or key location')

    try:
        rsrc = tls.lzh.open_resource(name=id_)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{id_} is not encrypted')
        config = tls.lzh.resource_cryptography_config(**props)
        crypto.change_key(info=config)
    except (ZFSException, ValueError) as e:
        ctx.logger.error(f'Failed to change key for {id_}', exc_info=True)
        raise CallError(f'Failed to change key for {id_}: {e}')


def change_encryption_root(tls: threading.local, id_: str) -> None:
    try:
        rsrc = tls.lzh.open_resource(name=id_)
        if (crypto := rsrc.crypto()) is None:
            raise CallError(f'{id_} is not encrypted')
        crypto.inherit_key()
    except (ZFSException, ValueError) as e:
        raise CallError(f'Failed to change encryption root for {id_}: {e}')


def bulk_check(ctx: 'ServiceContext', tls: threading.local, params: Iterable[CheckKeyParams]) -> list[CheckKeyResult]:
    statuses = []
    for i in params:
        result = error = None
        try:
            result = check_key(ctx, tls, **i)
        except Exception as e:
            error = str(e)
        finally:
            statuses.append({'result': result, 'error': error})

    return statuses
