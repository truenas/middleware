from middlewared.service import Service, private
from middlewared.service_exception import CallError
from middlewared.utils import run
from middlewared.plugins.smb import SMBCmd, SMBBuiltin

import re

RE_NETGROUPMAP = re.compile(r"^(?P<ntgroup>.+) \((?P<SID>S-[0-9\-]+)\) -> (?P<unixgroup>.+)$")


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @private
    async def groupmap_list(self):
        groupmap = []
        out = await run([SMBCmd.NET.value, 'groupmap', 'list'], check=False)
        if out.returncode != 0:
            raise CallError(f'groupmap list failed with error {out.stderr.decode()}')
        for line in (out.stdout.decode()).splitlines():
            m = RE_NETGROUPMAP.match(line)
            if m:
                groupmap.append(m.groupdict())

        return groupmap

    @private
    async def add_builtin_group(self, group):
        unixgroup = group
        ntgroup = group[8:].capitalize()
        sid = SMBBuiltin[ntgroup.upper()].value[1]
        gm_add = await run([
            SMBCmd.NET.value, '-d', '0', 'groupmap', 'add', f'sid={sid}',
            'type=builtin', f'unixgroup={unixgroup}', f'ntgroup={ntgroup}'],
            check=False
        )
        if gm_add.returncode != 0:
            raise CallError(
                f'Failed to generate groupmap for [{group}]: ({gm_add.stderr.decode()})'
            )

    @private
    async def groupmap_add(self, group):
        """
        Map Unix group to NT group. This is required for group members to be
        able to access the SMB share. Name collisions with well-known and
        builtin groups must be avoided. Mapping groups with the same
        names as users should also be avoided.
        """
        passdb_backend = await self.middleware.call('smb.getparm', 'passdb backend', 'global')
        if passdb_backend == 'ldapsam':
            return

        if group in SMBBuiltin.unix_groups():
            return await self.add_builtin_group(group)

        disallowed_list = ['USERS', 'ADMINISTRATORS', 'GUESTS']
        existing_groupmap = await self.middleware.call('smb.groupmap_list')

        for user in (await self.middleware.call('user.query')):
            disallowed_list.append(user['username'].upper())

        for g in existing_groupmap:
            disallowed_list.append(g['ntgroup'].upper())

        if group.upper() in disallowed_list:
            self.logger.debug('Setting group map for %s is not permitted', group)
            return False
        gm_add = await run(
            [SMBCmd.NET.value, '-d', '0', 'groupmap', 'add', 'type=local', f'unixgroup={group}', f'ntgroup={group}'],
            check=False
        )
        if gm_add.returncode != 0:
            raise CallError(
                f'Failed to generate groupmap for [{group}]: ({gm_add.stderr.decode()})'
            )

    @private
    async def groupmap_delete(self, ntgroup=None, sid=None):
        if not ntgroup and not sid:
            raise CallError("ntgroup or sid is required")

        if ntgroup:
            target = f"ntgroup={ntgroup}"
        elif sid:
            target = f"sid={sid}"

        gm_delete = await run(
            [SMBCmd.NET.value, '-d' '0', 'groupmap', 'delete', target], check=False
        )

        if gm_delete.returncode != 0:
            self.logger.debug(f'Failed to delete groupmap for [{target}]: ({gm_delete.stderr.decode()})')
