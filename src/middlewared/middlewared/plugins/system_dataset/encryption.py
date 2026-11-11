"""
This module sets up a system dataset that the pwenc secret encrypts. The secret is 32 random bytes, so ZFS uses it
as a raw key. ZFS reads the key from its file, so middleware never loads the secret.
"""

import errno
from typing import Any

from middlewared.plugins.zfs.create_impl import create_leaf
from middlewared.plugins.zfs.encryption import change_key, check_key, load_key
from middlewared.plugins.zfs.utils import open_resource
from middlewared.service_exception import CallError
from middlewared.utils.pwenc import PWENC_KEY_LOCATION

# What to do about a dataset that setup_pwenc_dataset refuses.
_RECOVERY = "Destroy it. At the next boot, middleware makes a new one, and TrueSearch builds its indexes again."


def setup_pwenc_dataset(tls: Any, dataset: str, props: dict[str, Any], encryption: str | None) -> bool:
    """
    Make sure that `dataset` exists, is encrypted with the pwenc secret, and has its key loaded. `encryption` is the
    raw value of the encryption property of the dataset, or None if the dataset does not exist. Return True if the
    dataset was made with `props`.

    Raise `CallError` if the dataset is not encrypted, or if the pwenc secret does not unlock it. This function
    destroys nothing. The second case occurs after the pwenc secret changes without a configuration upload, for
    example when a new installation imports the pool. A configuration upload wraps the key again with
    `rekey_pwenc_dataset`.
    """
    if encryption is None:
        crypto = tls.lzh.resource_cryptography_config(keyformat="raw", keylocation=PWENC_KEY_LOCATION)
        create_leaf(tls, dataset, "FILESYSTEM", {str(name): value for name, value in props.items()}, {}, crypto)
        return True

    if encryption == "off":
        raise CallError(f"{dataset} is not encrypted. {_RECOVERY}", errno.EINVAL)

    crypto = open_resource(tls, dataset).crypto()
    if crypto is not None and crypto.info().key_is_loaded:
        return False

    if not check_key(tls, dataset, key_location=PWENC_KEY_LOCATION):
        raise CallError(f"The pwenc secret of this system does not unlock {dataset}. {_RECOVERY}", errno.EACCES)

    load_key(tls, dataset, key_location=PWENC_KEY_LOCATION)
    return False


def rekey_pwenc_dataset(tls: Any, dataset: str, secret_path: str) -> None:
    """
    Wrap the key of `dataset` with the pwenc secret at `secret_path`. ZFS reads the new key from that file. The key
    location stays the pwenc secret file of this system, so the dataset unlocks after `secret_path` replaces that
    file. The key of the dataset must be loaded.
    """
    change_key(tls, dataset, {"keyformat": "raw", "keylocation": f"file://{secret_path}"})
    open_resource(tls, dataset).set_properties(properties={"keylocation": PWENC_KEY_LOCATION})
