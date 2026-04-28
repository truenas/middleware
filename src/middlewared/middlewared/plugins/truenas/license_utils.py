from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import date
import logging
import os
import shutil
import time
import typing

from truenas_os_pyutils.io import atomic_write
from truenas_pylicensed import LicenseStatus, LicenseType, verify

from middlewared.service import CallError, ValidationError

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware

logger = logging.getLogger(__name__)

__all__ = (
    "LICENSE_FILE",
    "FeatureInfo",
    "LicenseInfo",
    "upload_license",
    "get_license_info",
    "configure_ha_license",
)

LICENSE_DIR = "/data/subsystems/truenas_license"
LICENSE_FILE = f"{LICENSE_DIR}/license"
LICENSE_BACKUP = f"{LICENSE_DIR}/license.bak"


@dataclass(frozen=True, kw_only=True, slots=True)
class FeatureInfo:
    name: str
    """Feature key (e.g. "DEDUP", "SED")."""
    start_date: date | None
    """Feature start date or None."""
    expires_at: date | None
    """Feature expiration date or None for perpetual."""


@dataclass(frozen=True, kw_only=True, slots=True)
class LicenseInfo:
    id: str
    """Unique UUID string for the license."""
    type: LicenseType
    """The license type."""
    model: str | None
    """Hardware model (e.g. "H30") for enterprise types, None otherwise."""
    expires_at: date | None
    """Synthesized expiration: top-level expires_at for test licenses,
    SUPPORT feature expires_at for all other types."""
    features: list[FeatureInfo]
    """Licensed features."""
    serials: list[str]
    """System serial number(s) for hardware-bound licenses."""
    enclosures: dict[str, int]
    """Licensed enclosure models mapped to count."""
    contract_type: str | None
    """Support contract type."""


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
            "License daemon did not reload after upload (reload_seq unchanged). "
            "The daemon may be unresponsive.",
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


def get_license_info(lic: LicenseStatus | None = None) -> LicenseInfo | None:
    """Query the daemon for the current license. Returns None if no valid license."""
    if lic is None:
        lic = verify()

    if not lic.valid:
        return None

    support = lic.features.get("SUPPORT") if lic.features else None

    if support:
        contract_type: str | None = support.type
    else:
        contract_type = None

    if lic.expires_at:
        expires_at: date | None = date.fromisoformat(lic.expires_at)
    elif support and support.expires_at:
        expires_at = date.fromisoformat(support.expires_at)
    else:
        expires_at = None

    return LicenseInfo(
        id=lic.id,  # type: ignore[arg-type]
        type=lic.type,  # type: ignore[arg-type]
        model=lic.model,
        expires_at=expires_at,
        features=[
            FeatureInfo(
                name=name,
                start_date=date.fromisoformat(f.start_date) if f.start_date else None,
                expires_at=date.fromisoformat(f.expires_at) if f.expires_at else None,
            )
            for name, f in (lic.features or {}).items()
        ],
        serials=lic.system_id["serials"] if lic.system_id else [],
        enclosures={
            model: entry["count"] for model, entry in (lic.enclosures or {}).items()
        },
        contract_type=contract_type,
    )


def configure_ha_license(middleware: Middleware) -> None:
    try:
        middleware.call_sync("failover.ensure_remote_client")
    except Exception as e:
        # this is fatal because we can't determine what the remote ip address
        # is to so any failover.call_remote calls will fail
        raise ValidationError("license", f"Failed to determine remote heartbeat IP address: {e}")

    try:
        middleware.call_sync("failover.call_remote", "failover.ensure_remote_client")
    except Exception:
        # this is not fatal, so no reason to return early
        # it just means that any "failover.call_remote" calls initiated from the remote node
        # will fail but that shouldn't be happening anyway
        logger.warning(
            "Remote node failed to determine this nodes heartbeat IP address",
            exc_info=True,
        )

    try:
        middleware.call_sync("failover.send_license")
    except Exception:
        logger.warning("Failed to send file to remote node", exc_info=True)
