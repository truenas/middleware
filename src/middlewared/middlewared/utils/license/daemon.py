"""Talk to the license daemon and normalize what it reports."""

from __future__ import annotations

import base64
import contextlib
from datetime import date
import json
import logging
import os
import shutil
import time
from types import MappingProxyType
import typing

from truenas_os_pyutils.io import atomic_write
from truenas_pylicensed import FEATURE_NAME_MAP, LicenseStatus, get_fingerprint, verify

from middlewared.service_exception import CallError

from .constants import LICENSE_BACKUP, LICENSE_DIR, LICENSE_FILE
from .types import FeatureInfo, LicenseInfo

logger = logging.getLogger(__name__)

__all__ = (
    "from_license_status",
    "get_fingerprint_b64",
    "upload_license",
)


def get_fingerprint_b64() -> str:
    """Return the system hardware fingerprint as a base64-encoded
    JSON string suitable for the license signing server."""
    daemon_fp = get_fingerprint()
    smbios = typing.cast(dict[str, typing.Any], daemon_fp.get("smbios", {}))
    flat: dict[str, typing.Any] = {
        "macs": daemon_fp.get("macs", []),
        "cpu_id": daemon_fp["cpu_id"],
        "machine_id": daemon_fp["machine_id"],
    }
    for flat_key, smbios_key in (
        ("smbios_uuid", "uuid"),
        ("product_serial", "product_serial"),
        ("chassis_serial", "chassis_serial"),
        ("board_serial", "board_serial"),
    ):
        component = smbios.get(smbios_key, {})
        if component.get("available"):
            flat[flat_key] = component.get("value")
        else:
            flat[flat_key] = None
    return base64.b64encode(json.dumps(flat).encode()).decode()


@typing.overload
def _wait_for_reload_seq_change(seq: int, error_msg: str, raise_: typing.Literal[True] = ...) -> LicenseStatus: ...


@typing.overload
def _wait_for_reload_seq_change(seq: int, error_msg: str, raise_: typing.Literal[False]) -> LicenseStatus | None: ...


def _wait_for_reload_seq_change(seq: int, error_msg: str, raise_: bool = True) -> LicenseStatus | None:
    """Poll verify() until reload_seq differs from *seq*, returning the new status.

    If the sequence does not change within ~3 seconds, raises CallError when
    raise_=True (default) or logs an error and returns None when raise_=False.
    """
    lic = verify()
    for _ in range(6):
        if lic.reload_seq != seq:
            return lic

        time.sleep(0.5)
        lic = verify()

    if raise_:
        raise CallError(error_msg)

    logger.error(error_msg)
    return None


@contextlib.contextmanager
def upload_license(license_pem: str) -> typing.Generator[LicenseStatus, None, None]:
    """Write a license to disk, verify via daemon, roll back on failure.

    Used as a context manager: yields the validated LicenseStatus so the
    caller can perform follow-up work inside the ``with`` block.  If the
    block raises an exception the previously installed license is restored.
    """
    os.makedirs(LICENSE_DIR, mode=0o700, exist_ok=True)

    # Snapshot the current reload_seq so we can detect when the daemon
    # has picked up and processed the new file via inotify
    initial_seq = verify().reload_seq

    # Back up existing license so we can restore on validation failure
    try:
        shutil.copy2(LICENSE_FILE, LICENSE_BACKUP)
        had_backup = True
    except FileNotFoundError:
        had_backup = False

    lic = None
    try:
        # Write the new license to disk -- daemon picks this up via inotify
        with atomic_write(LICENSE_FILE, "w", perms=0o600) as f:
            f.write(license_pem)

        # Wait for the daemon to reload the new license
        lic = _wait_for_reload_seq_change(
            initial_seq,
            "License daemon did not reload after upload (reload_seq unchanged). The daemon may be unresponsive.",
        )

        yield lic
    except Exception:
        try:
            if had_backup:
                shutil.move(LICENSE_BACKUP, LICENSE_FILE)
            else:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(LICENSE_FILE)

            if lic is not None:
                # Wait for the daemon to acknowledge the rollback
                _wait_for_reload_seq_change(
                    lic.reload_seq,
                    "License daemon did not reload after rollback (reload_seq unchanged). "
                    "The daemon may be unresponsive.",
                    raise_=False,
                )
        except Exception as e:
            logger.error("Error rolling back license: %r", e)

        raise

    # Success -- clean up backup
    if had_backup:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(LICENSE_BACKUP)


def from_license_status(status: LicenseStatus | None = None) -> LicenseInfo | None:
    """Normalize a daemon LicenseStatus. Returns None if no valid license."""
    if status is None:
        status = verify()

    if not status.valid:
        return None

    support = status.features.get("SUPPORT") if status.features else None

    if support:
        contract_type: str | None = support.type
    else:
        contract_type = None

    features: dict[str, FeatureInfo] = {}
    for name, f in (status.features or {}).items():
        key = str(FEATURE_NAME_MAP.get(name, name))
        features[key] = FeatureInfo(
            name=key,
            start_date=date.fromisoformat(f.start_date) if f.start_date else None,
            expires_at=date.fromisoformat(f.expires_at) if f.expires_at else None,
            source=f.source,
            type=f.type,
        )

    return LicenseInfo(
        id=status.id,  # type: ignore[arg-type]
        type=status.type,  # type: ignore[arg-type]
        model=status.model,
        support_expires_at=date.fromisoformat(support.expires_at) if support and support.expires_at else None,
        features=MappingProxyType(features),
        serials=tuple(status.system_id["serials"]) if status.system_id else (),
        enclosures=MappingProxyType(
            {model: entry["count"] for model, entry in (status.enclosures or {}).items()}
        ),
        contract_type=contract_type,
    )
