import contextlib
import os
import shutil

import truenas_pylicensed
from truenas_os_pyutils.io import atomic_write

from middlewared.service import ValidationError


LICENSE_DIR = "/data/truenas"
LICENSE_FILE = f"{LICENSE_DIR}/license"
LICENSE_BACKUP = "/data/truenas/license.bak"


def upload_license(license_pem: str) -> None:
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
    result = truenas_pylicensed.verify()
    if not result.valid:
        # Roll back: restore backup or remove the bad file
        if had_backup:
            shutil.move(LICENSE_BACKUP, LICENSE_FILE)
        else:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(LICENSE_FILE)

        raise ValidationError("truenas.license.upload", result.error)

    # Success -- clean up backup
    if had_backup:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(LICENSE_BACKUP)


def get_license_info() -> dict | None:
    """Query the daemon for the current license. Returns None if no valid license."""
    result = truenas_pylicensed.verify()
    if not result.valid:
        return None

    return {
        "id": result.id,
        "version": result.version,
        "type": result.type,
        "model": result.model,
        "expires_at": result.expires_at,
        "features": result.features,
        "enclosures": result.enclosures,
        "sf": result.sf,
        "tnc": result.tnc,
        "system_id": result.system_id,
        "fingerprint": result.fingerprint,
    }
