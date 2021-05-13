import contextlib
import os
import textwrap

from middlewared.service import private, Service


class SMBService(Service):
    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @private
    async def disable_acl_if_trivial(self):
        share_ids = await self.middleware.call("keyvalue.get", "smb_disable_acl_if_trivial", [])
        if not share_ids:
            return

        share_ids = set(share_ids)
        for share in await self.middleware.call("sharing.smb.query", [("locked", "=", False), ("enabled", "=", True)]):
            if share["id"] not in share_ids:
                continue

            try:
                acl_is_trivial = await self.middleware.call("filesystem.acl_is_trivial", share["path"])
            except Exception:
                self.middleware.logger.warning("Error running filesystem.acl_is_trivial for share %r", share["id"],
                                               exc_info=True)
                continue

            if acl_is_trivial:
                self.middleware.logger.info("ACL is trivial for migrated AFP share %r, disabling ACL", share["id"])
                await self.middleware.call(
                    "datastore.update", "sharing.cifs_share", share["id"], {"cifs_acl": False},
                )
            else:
                self.middleware.logger.info("ACL is not trivial for migrated AFP share %r, not disabling ACL",
                                            share["id"])

            share_ids.discard(share["id"])

        if share_ids:
            await self.middleware.call("keyvalue.set", "smb_disable_acl_if_trivial", list(share_ids))
        else:
            await self.middleware.call("keyvalue.delete", "smb_disable_acl_if_trivial")
