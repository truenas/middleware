import hashlib
import logging
import os
import base64

from middlewared.utils import run

logger = logging.getLogger(__name__)
kdir = "/etc/kerberos"
keytabfile = "/etc/krb5.keytab"
ktutil_cmd = "/usr/sbin/ktutil"

async def shasum_system_keytab():
    with open(keytabfile, 'rb') as f:
        system_keytab = f.read()

    return hashlib.sha256(system_keytab).hexdigest()


async def must_update_samba_keytab(middleware):
    if not await middleware.call('cache.has_key', 'keytab_shasum'):
        await middleware.call('cache.put', 'keytab_shasum', await shasum_system_keytab())
        return True
    else:
        cached_shasum = await middleware.call('cache.get', 'keytab_shasum')
        kt_shasum = await shasum_system_keytab()
        if cached_shasum != kt_shasum:
            await middleware.call('cache.put', 'keytab_shasum', kt_sum)
            return True

    return False 


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
    """
    Samba may end up changing the keytab associated with the AD machine account
    behind the scenes. These changes should not be overwritten, and so if the
    system keytab has changed since the last time we generated it, assume samba
    has done something and save the current samba keytab in the database. 
    """
    if await must_update_samba_keytab(middleware):
        await middleware.call('kerberos.keytab.store_samba_keytab')
    keytabs = await middleware.call('kerberos.keytab.query')
    if not keytabs:
        logger.debug(f'No keytabs in configuration database, skipping keytab generation')
        return

    for keytab in keytabs:
        db_keytabfile = base64.b64decode(keytab['file'].encode())
        db_keytabname = keytab['name']
        await write_keytab(db_keytabname, db_keytabfile)
