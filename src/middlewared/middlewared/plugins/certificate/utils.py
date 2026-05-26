from __future__ import annotations

from typing import Any

from truenas_crypto_utils.key import export_private_key

# Cert locations
CERT_ROOT_PATH = "/etc/certificates"
DEFAULT_CERT_NAME = "truenas_default"

# Defining cert constants being used
CERT_TYPE_EXISTING = 0x08
CERT_TYPE_CSR = 0x20


def get_cert_info_from_data(data: dict[str, Any]) -> dict[str, Any]:
    cert_info_keys = [
        "key_length",
        "country",
        "state",
        "city",
        "organization",
        "common",
        "key_type",
        "ec_curve",
        "san",
        "serial",
        "email",
        "lifetime",
        "digest_algorithm",
        "organizational_unit",
    ]
    return {key: data.get(key) for key in cert_info_keys if data.get(key)}


def get_private_key(privatekey: str | None = None, passphrase: str | None = None) -> str | None:
    if passphrase is None:
        return privatekey

    if privatekey is None:
        raise ValueError("Must provide privatekey")

    return export_private_key(privatekey, passphrase)
