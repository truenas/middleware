import logging
import os
import base64
import subprocess
import stat

from contextlib import suppress
from middlewared.plugins.etc import FileShouldNotExist

logger = logging.getLogger(__name__)
kdir = "/etc/kerberos"
keytabfile = "/etc/krb5.keytab"
unified_keytab = os.path.join(kdir, 'tmp_keytab')


def mit_copy(temp_keytab):
    kt_copy = subprocess.run(
        ['ktutil'],
        input=f'rkt {temp_keytab}\nwkt {unified_keytab}'.encode(),
        capture_output=True
    )
    if kt_copy.stderr:
        logger.error("%s: failed to add to uinified keytab: %s",
                     temp_keytab, kt_copy.stderr.decode())


def write_keytab(db_keytabname, db_keytabfile):
    dirfd = None

    def opener(path, flags):
        return os.open(path, flags, mode=0o600, dir_fd=dirfd)

    with suppress(FileExistsError):
        os.mkdir(kdir, mode=0o700)

    try:
        dirfd = os.open(kdir, os.O_DIRECTORY)
        st = os.fstat(dirfd)
        if stat.S_IMODE(st.st_mode) != 0o700:
            os.fchmod(dirfd, 0o700)

        with open(db_keytabname, "wb", opener=opener) as f:
            f.write(db_keytabfile)
            kt_name = os.readlink(f'/proc/self/fd/{f.fileno()}')

        mit_copy(kt_name)
        os.remove(db_keytabname, dir_fd=dirfd)

    finally:
        os.close(dirfd)


def render(service, middleware, render_ctx):
    keytabs = middleware.call_sync('kerberos.keytab.query')
    if not keytabs:
        raise FileShouldNotExist

    for keytab in keytabs:
        db_keytabfile = base64.b64decode(keytab['file'].encode())
        db_keytabname = f'keytab_{keytab["id"]}'
        write_keytab(db_keytabname, db_keytabfile)

    with open(unified_keytab, 'rb') as f:
        keytab_bytes = f.read()

    os.unlink(unified_keytab)
    return keytab_bytes
