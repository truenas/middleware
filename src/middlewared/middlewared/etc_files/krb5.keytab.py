import logging
import os
import base64
import stat
import subprocess
from contextlib import suppress

logger = logging.getLogger(__name__)
kdir = "/etc/kerberos"
keytabfile = "/etc/krb5.keytab"
ktutil_cmd = "/usr/sbin/ktutil"


def set_mode(fd, mode):
    if stat.S_IMODE(os.fstat(fd).st_mode) != mode:
        os.fchmod(fd, mode)


def write_keytab(db_keytabname, db_keytabfile):
    def opener(path, flags):
        return os.open(path, flags, dir_fd=dirfd, mode=0o600)

    with suppress(FileExistsError):
        os.mkdir(kdir, mode=0o700)

    try:
        dirfd = os.open(kdir, os.O_DIRECTORY)
        set_mode(dirfd, 0o700)

        with open(db_keytabname, "wb", opener=opener) as f:
            set_mode(f.fileno(), 0o600)
            f.write(db_keytabfile)

        ktutil = subprocess.run([
            ktutil_cmd, "copy", f'{kdir}/{db_keytabname}', keytabfile
        ], check=False, capture_output=True)

        if ktutil.stderr:
            logger.debug("%s: keytab generation failed: %s",
                         db_keytabname, ktutil.stderr.decode())

        os.remove(db_keytabname, dir_fd=dirfd)

    finally:
        os.close(dirfd)


def render(service, middleware):
    keytabs = middleware.call_sync('kerberos.keytab.query')
    if not keytabs:
        logger.trace('No keytabs in configuration database, skipping keytab generation')
        return

    for keytab in keytabs:
        db_keytabfile = base64.b64decode(keytab['file'].encode())
        db_keytabname = f'keytab_{keytab["id"]}'
        write_keytab(db_keytabname, db_keytabfile)
