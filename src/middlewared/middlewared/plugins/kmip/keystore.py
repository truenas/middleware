# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions


class KMIPKeyStore:
    """
    In-memory cache of ZFS/SED encryption keys.

    The system never queries the KMIP server directly while using a key. Instead the keys are
    cached here on boot and kept in sync, and all key-related tasks rely on this cache.
    """

    def __init__(self) -> None:
        self.zfs_keys: dict[str, str] = {}
        self.disks_keys: dict[str, str] = {}
        self.global_sed_key: str = ""
