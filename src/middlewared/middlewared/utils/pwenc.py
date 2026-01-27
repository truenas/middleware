import os
import threading
import uuid

import truenas_pypwenc

__all__ = ['PWENC_FILE_SECRET', 'PWENC_FILE_SECRET_MODE', 'pwenc_rename', 'pwenc_encrypt', 'pwenc_decrypt',
           'pwenc_generate_secret']


PWENC_PADDING = b'{'  # This is for legacy compatibility. aes-256-ctr doesn't need padding
PWENC_FILE_SECRET = truenas_pypwenc.DEFAULT_SECRET_PATH
PWENC_FILE_SECRET_MODE = 0o600
global_ctx = None
lock = threading.Lock()


def pwenc_get_ctx() -> truenas_pypwenc.PwencContext:
    """ Retrieve a truenas_pypwenc() context with secret key
    loaded in memfd secret. This will raise an exception if file
    does not exist. """
    global global_ctx

    if global_ctx is not None:
        return global_ctx

    with lock:
        # check again under lock to ensure we don't have a race on another thread generating a context
        if global_ctx is None:
            global_ctx = truenas_pypwenc.get_context(create=False, watch=True)

    return global_ctx


def pwenc_rename(source_path: str) -> None:
    """ Atomically replace pwenc secret file and reset cache.

    This function:
    - Acquires lock to prevent concurrent access
    - Ensures source file has correct permissions
    - Uses atomic rename to replace the pwenc secret file
    - Resets cache after successful rename

    Args:
        source_path: Path to file that will replace the pwenc secret

    Raises:
        OSError: If chmod/chown/rename fails
        FileNotFoundError: If source_path doesn't exist
    """
    with lock:
        # In addition to validating the permissions, this ensures
        # that the source_path actually exists
        os.chmod(source_path, PWENC_FILE_SECRET_MODE)
        os.chown(source_path, 0, 0)
        backup_name = f'{PWENC_FILE_SECRET}_old.{uuid.uuid4()}'
        backup_created = False

        try:
            os.rename(PWENC_FILE_SECRET, backup_name)
            backup_created = True
        except FileNotFoundError:
            pass

        try:
            os.rename(source_path, PWENC_FILE_SECRET)
        except Exception:
            # Someone maybe removed source_path from under us put the original file back and re-raise error
            if backup_created:
                os.rename(backup_name, PWENC_FILE_SECRET)
            raise


def pwenc_encrypt(data_in: bytes) -> bytes:
    """ Encrypt and base64 encode the input bytes """
    global global_ctx

    ctx = pwenc_get_ctx()
    try:
        return ctx.encrypt(data_in)
    except truenas_pypwenc.PwencError as exc:
        if exc.code != truenas_pypwenc.PWENC_ERROR_SECRET_RELOAD_FAILED:
            raise

        # If we fail to reload secret after change out from under us force creation of new pwenc handle and retry.
        # This may be a simple toctou issue, but minimally it will give the caller a descriptive error in case the
        # secrets file doesn't exist anymore
        global_ctx = None
        ctx = pwenc_get_ctx()
        return ctx.encrypt(data_in)


def pwenc_decrypt(data_in: bytes) -> bytes:
    """ Base64 decode and decrypt the input bytes """
    global global_ctx

    ctx = pwenc_get_ctx()
    try:
        return ctx.decrypt(data_in).rstrip(PWENC_PADDING)
    except truenas_pypwenc.PwencError as exc:
        if exc.code != truenas_pypwenc.PWENC_ERROR_SECRET_RELOAD_FAILED:
            raise

        # If we fail to reload secret after change out from under us force creation of new pwenc handle and retry.
        # This may be a simple toctou issue, but minimally it will give the caller a descriptive error in case the
        # secrets file doesn't exist anymore
        global_ctx = None
        ctx = pwenc_get_ctx()
        return ctx.decrypt(data_in).rstrip(PWENC_PADDING)


def pwenc_generate_secret() -> None:
    """ Create a new pwenc secret. """
    with lock:
        try:
            os.rename(PWENC_FILE_SECRET, f'{PWENC_FILE_SECRET}_old.{uuid.uuid4()}')
        except FileNotFoundError:
            pass

        # We do not store this pwenc context since it was created with the create=True flag and we don't want the watch
        # to recreate on reload. Next caller can get the context properly
        ctx = truenas_pypwenc.get_context(create=True, watch=True)
        assert ctx.created


def encrypt(decrypted: str) -> str:
    """ Encrypt the input data string and return a base64 string """
    data = decrypted.encode('utf8')
    encrypted = pwenc_encrypt(data)
    return encrypted.decode()


def decrypt(encrypted: str, _raise: bool = False) -> str:
    """ Decrypt the input base64 string and return a string """
    if not encrypted:
        return ''

    data = encrypted.encode('utf8')

    try:
        decrypted = pwenc_decrypt(data)
        return decrypted.decode('utf8')
    except Exception:
        if _raise:
            raise
        return ''
