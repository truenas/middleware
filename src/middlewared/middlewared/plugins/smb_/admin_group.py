from middlewared.service import Service, ValidationErrors, private
from middlewared.service_exception import CallError
from middlewared.utils import run
from middlewared.plugins.smb import SMBCmd, WBCErr


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @private
    async def validate_admin_groups(self, sid):
        """
        Check if group mapping already exists because 'net groupmap addmem' will fail
        if the mapping exists. Remove any entries that should not be present. Extra
        entries here can pose a significant security risk. The only default entry will
        have a RID value of "512" (Domain Admins).
        In LDAP environments, members of S-1-5-32-544 cannot be removed without impacting
        the entire LDAP environment because this alias exists on the remote LDAP server.
        """
        sid_is_present = False
        if await self.middleware.call('ldap.get_state') != 'DISABLED':
            self.logger.debug("As a safety precaution, extra alias entries for S-1-5-32-544"
                              "cannot be removed while LDAP is enabled. Skipping removal.")
            return True
        listmem = await run([SMBCmd.NET.value, 'groupmap', 'listmem', 'S-1-5-32-544'], check=False)
        member_list = listmem.stdout.decode()
        if not member_list:
            return True

        for group in member_list.splitlines():
            group = group.strip()
            if group == sid:
                self.logger.debug("SID [%s] is already a member of BUILTIN\\administrators", sid)
                sid_is_present = True
            if group.rsplit('-', 1)[-1] != "512" and group != sid:
                self.logger.debug(f"Removing {group} from local admins group.")
                rem = await run([SMBCmd.NET.value, 'groupmap', 'delmem', 'S-1-5-32-544', group], check=False)
                if rem.returncode != 0:
                    raise CallError(f'Failed to remove sid [{sid}] from S-1-5-32-544: {rem.stderr.decode()}')

        if sid_is_present:
            return False
        else:
            return True

    @private
    async def wbinfo_gidtosid(self, gid):
        verrors = ValidationErrors()
        proc = await run([SMBCmd.WBINFO.value, '--gid-to-sid', str(gid)], check=False)
        if proc.returncode != 0:
            if WBCErr.WINBIND_NOT_AVAILABLE.err() in proc.stderr.decode():
                return WBCErr.WINBIND_NOT_AVAILABLE.err()
            else:
                verrors.add('smb_update.admin_group',
                            f'Failed to identify Windows SID for gid [{gid}]: {proc.stderr.decode()}')
                raise verrors

        return proc.stdout.decode().strip()

    @private
    async def add_admin_group(self, admin_group=None, check_deferred=False):
        """
        Add a local or directory service group to BUILTIN\\Administrators (S-1-5-32-544)
        Members of this group have elevated privileges to the Samba server (ability to
        take ownership of files, override ACLs, view and modify user quotas, and administer
        the server via the Computer Management MMC Snap-In. Unfortuntely, group membership
        must be managed via "net groupmap listmem|addmem|delmem", which requires that
        winbind be running when the commands are executed. In this situation, net command
        will fail with WBC_ERR_WINBIND_NOT_AVAILABLE. If this error message is returned, then
        flag for a deferred command retry when service starts.

        `admin_group` This is the group to add to BUILTIN\\Administrators. If unset, then
            look up the value in the config db.
        `check_deferred` If this is True, then only perform the group mapping if this has
            been flagged as in need of deferred setup (i.e. Samba wasn't running when it was initially
            called). This is to avoid unecessarily calling during service start.
        """

        verrors = ValidationErrors()
        if check_deferred:
            is_deferred = await self.middleware.call('cache.has_key', 'SMB_SET_ADMIN')
            if not is_deferred:
                self.logger.debug("No cache entry indicating delayed action to add admin_group was found.")
                return True
            else:
                await self.middleware.call('cache.pop', 'SMB_SET_ADMIN')

        if not admin_group:
            smb = await self.middleware.call('smb.config')
            admin_group = smb['admin_group']

        # We must use GIDs because wbinfo --name-to-sid expects a domain prefix "FREENAS\user"
        group = await self.middleware.call("dscache.get_uncached_group", admin_group)
        if not group:
            verrors.add('smb_update.admin_group', f"Failed to validate group: {admin_group}")
            raise verrors

        sid = await self.wbinfo_gidtosid(group['gr_gid'])
        if sid == WBCErr.WINBIND_NOT_AVAILABLE.err():
            self.logger.debug("Delaying admin group add until winbind starts")
            await self.middleware.call('cache.put', 'SMB_SET_ADMIN', True)
            return True

        must_add_sid = await self.validate_admin_groups(sid)
        if not must_add_sid:
            return True

        proc = await run([SMBCmd.NET.value, 'groupmap', 'addmem', 'S-1-5-32-544', sid],
                         check=False)
        if proc.returncode != 0:
            raise CallError(f'net groupmap addmem failed: {proc.stderr.decode().strip()}')

        self.logger.debug("Successfully added [%s] to BUILTIN\\Administrators", admin_group)
        return True
