from __future__ import annotations

from typing import Any

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
    return {key: value for key in cert_info_keys if (value := data.get(key))}
