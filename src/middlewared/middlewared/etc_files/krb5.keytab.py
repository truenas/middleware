import logging
import os
import base64

from middlewared.utils import run

logger = logging.getLogger(__name__)
kdir = "/etc/kerberos"
keytabfile = "/etc/krb5.keytab"
ktutil_cmd = "/usr/sbin/ktutil"


async def write_keytab(db_keytabname, db_keytabfile):
    temp_keytab = f'{kdir}/{db_keytabname}'
    if not os.path.exists(kdir):
        os.mkdir(kdir)
    if os.path.exists(temp_keytab):
        os.remove(temp_keytab)
    with open(temp_keytab, "wb") as f:
        f.write(db_keytabfile)

    ktutil = await run([ktutil_cmd, "copy", temp_keytab, keytabfile], check=False)
    ktutil_errs = ktutil.stderr.decode()

    if ktutil_errs:
        logger.debug(f'Keytab generation failed with error: {ktutil_errs}')

    os.remove(temp_keytab)


async def render(service, middleware):
    keytabs = await middleware.call("datastore.query", "directoryservice.kerberoskeytab")
    if not keytabs:
        logger.debug(f'No keytabs in configuration database, skipping keytab generation')
        return

    for keytab in keytabs:
        db_keytabfile = base64.b64decode(keytab['keytab_file'])
        db_keytabname = keytab['keytab_name']
        await write_keytab(db_keytabname, db_keytabfile)
