import contextlib
import os
import shutil
import time
import typing

from truenas_pylicensed import LicenseError, LicenseStatus, LicenseType, verify
from truenas_os_pyutils.io import atomic_write

from middlewared.service import ValidationError

__all__ = (
    "FeatureInfo",
    "LicenseInfo",
    "upload_license",
    "get_license_info",
    "configure_ha_license",
)

LICENSE_DIR = "/data/truenas"
LICENSE_FILE = f"{LICENSE_DIR}/license"
LICENSE_BACKUP = "/data/truenas/license.bak"
if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


class FeatureInfo(typing.TypedDict):
    name: str
    """Feature key (e.g. "DEDUP", "SED")."""
    start_date: str | None
    """Feature start date (YYYY-MM-DD) or None."""
    expires_at: str | None
    """Feature expiration date (YYYY-MM-DD) or None for perpetual."""


class LicenseInfo(typing.TypedDict):
    id: str
    """Unique UUID string for the license."""
    type: LicenseType
    """The license type."""
    model: str | None
    """Hardware model (e.g. "H30") for enterprise types, None otherwise."""
    expires_at: str | None
    """Synthesized expiration: top-level expires_at for test licenses,
    SUPPORT feature expires_at for all other types."""
    features: list[FeatureInfo]
    """Licensed features."""
    serials: list[str]
    """System serial number(s) for hardware-bound licenses."""
    enclosures: dict[str, int]
    """Licensed enclosure models mapped to count."""


def upload_license(license_pem: str) -> LicenseStatus:
    """Write a license to disk, verify via daemon, roll back on failure."""
    os.makedirs(LICENSE_DIR, mode=0o700, exist_ok=True)

    # Back up existing license so we can restore on validation failure
    try:
        shutil.copy2(LICENSE_FILE, LICENSE_BACKUP)
        had_backup = True
    except FileNotFoundError:
        had_backup = False

    # Write the new license to disk -- daemon picks this up via inotify
    with atomic_write(LICENSE_FILE, "w") as f:
        f.write(license_pem)
    os.chmod(LICENSE_FILE, 0o600)

    # Let the daemon validate (schema, system ID, signature)
    lic = verify()
    if lic.code == LicenseError.NO_LICENSE:
        # 0.5 * 6 == 3 seconds
        for i in range(6):
            lic = verify()
            if lic.code == LicenseError.NO_LICENSE:
                # daemon uses inotify which could take a moment
                # so don't error here immediately, though, we're
                # talking milliseconds for normal behavior
                time.sleep(0.5)
            else:
                break

    if not lic.valid:
        # Roll back: restore backup or remove the bad file
        if had_backup:
            shutil.move(LICENSE_BACKUP, LICENSE_FILE)
        else:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(LICENSE_FILE)

        raise ValidationError("truenas.license.upload", lic.error)

    # Success -- clean up backup
    if had_backup:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(LICENSE_BACKUP)

    return lic


def get_license_info(lic: LicenseStatus | None = None) -> LicenseInfo | None:
    """Query the daemon for the current license. Returns None if no valid license."""
    if lic is None:
        lic = verify()
    if not lic.valid:
        return None

    # Synthesize expires_at: test licenses use top-level,
    # all others use the SUPPORT feature's expiry
    if lic.type == LicenseType.TEST:
        expires_at = lic.expires_at
    else:
        support = lic.features.get("SUPPORT") if lic.features else None
        expires_at = support.expires_at if support else None

    return LicenseInfo(
        id=lic.id,
        type=lic.type,
        model=lic.model,
        expires_at=expires_at,
        features=[
            FeatureInfo(name=name, start_date=f.start_date, expires_at=f.expires_at)
            for name, f in (lic.features or {}).items()
        ],
        serials=lic.system_id["serials"] if lic.system_id else [],
        enclosures={
            model: entry["count"] for model, entry in (lic.enclosures or {}).items()
        },
    )


def configure_ha_license(mw: Middleware) -> None:
    if not mw.middleware.call_sync("system.is_ha_capable"):
        raise ValidationError(
            "truenas.license.upload", "This is not an HA capable system"
        )

    try:
        mw.middleware.call_sync("failover.ensure_remote_client")
    except Exception as e:
        # this is fatal because we can't determine what the remote ip address
        # is to so any failover.call_remote calls will fail
        raise ValidationError(
            "truenas.license.updload",
            f"Failed to determine remote heartbeat IP address: {e}",
        )

    try:
        mw.middleware.call_sync("failover.call_remote", "failover.ensure_remote_client")
    except Exception:
        # this is not fatal, so no reason to return early
        # it just means that any "failover.call_remote" calls initiated from the remote node
        # will fail but that shouldn't be happening anyways
        mw.logger.warning(
            "Remote node failed to determine this nodes heartbeat IP address",
            exc_info=True,
        )

    try:
        mw.middleware.call_sync("failover.send_small_file", LICENSE_FILE)
    except Exception:
        mw.logger.warning("Failed to sync database to remote node", exc_info=True)

    try:
        mw.middleware.call_sync("failover.call_remote", "etc.generate", ["rc"])
    except Exception:
        mw.logger.warning("etc.generate failed on standby", exc_info=True)
