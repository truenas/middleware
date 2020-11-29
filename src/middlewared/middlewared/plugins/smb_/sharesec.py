from middlewared.schema import Bool, Dict, List, Str, Int
from middlewared.service import (accepts, filterable, private, periodic, CRUDService)
from middlewared.service_exception import CallError
from middlewared.utils import run, filter_list
from middlewared.plugins.smb import SMBCmd

import enum
import errno
import os
import re

RE_SHAREACLENTRY = re.compile(r"^ACL:(?P<ae_who_sid>.+):(?P<ae_type>.+)\/0x0\/(?P<ae_perm>.+)$")


class SIDType(enum.IntEnum):
    """
    Defined in MS-SAMR (2.2.2.3) and lsa.idl
    Samba's group mapping database will primarily contain SID_NAME_ALIAS entries (local groups)
    """
    NONE = 0
    USER = 1
    DOM_GROUP = 2
    DOMAIN = 3
    ALIAS = 4
    WELL_KNOWN_GROUP = 5
    DELETED = 6
    INVALID = 7
    UNKNOWN = 8
    COMPUTER = 9
    LABEL = 10


class ShareSec(CRUDService):

    class Config:
        namespace = 'smb.sharesec'
        cli_namespace = 'sharing.smb.sharesec'

    @private
    async def parse_share_sd(self, sd, options=None):
        """
        Parses security descriptor text returned from 'sharesec'.
        Optionally will resolve the SIDs in the SD to names.
        """

        if len(sd) == 0:
            return {}
        parsed_share_sd = {'share_name': None, 'share_acl': []}
        if options is None:
            options = {'resolve_sids': True}

        sd_lines = sd.splitlines()
        # Share name is always enclosed in brackets. Remove them.
        parsed_share_sd['share_name'] = sd_lines[0][1:-1]

        # ACL entries begin at line 5 in the Security Descriptor
        for i in sd_lines[5:]:
            acl_entry = {}
            m = RE_SHAREACLENTRY.match(i)
            if m is None:
                self.logger.debug(f'{i} did not match regex')
                continue

            acl_entry.update(m.groupdict())
            if (options.get('resolve_sids', True)) is True:
                wb = await run([SMBCmd.WBINFO.value, '--sid-to-name', acl_entry['ae_who_sid']], check=False)
                if wb.returncode == 0:
                    wb_ret = wb.stdout.decode()[:-3].split('\\')
                    sidtypeint = int(wb.stdout.decode().strip()[-1:])
                    acl_entry['ae_who_name'] = {'domain': None, 'name': None, 'sidtype': SIDType.NONE}
                    acl_entry['ae_who_name']['domain'] = wb_ret[0]
                    acl_entry['ae_who_name']['name'] = wb_ret[1]
                    acl_entry['ae_who_name']['sidtype'] = SIDType(sidtypeint).name
                else:
                    self.logger.debug(
                        'Failed to resolve SID (%s) to name: (%s)' % (acl_entry['ae_who_sid'], wb.stderr.decode())
                    )

            parsed_share_sd['share_acl'].append(acl_entry)

        return parsed_share_sd

    async def _sharesec(self, **kwargs):
        """
        wrapper for sharesec(1). This manipulates share permissions on SMB file shares.
        The permissions are stored in share_info.tdb, and apply to the share as a whole.
        This is in contrast with filesystem permissions, which define the permissions for a file
        or directory, and in the latter case may also define permissions inheritance rules
        for newly created files in the directory. The SMB Share ACL only affects access through
        the SMB protocol.
        """
        action = kwargs.get('action')
        share = kwargs.get('share', '')
        args = kwargs.get('args', '')
        sharesec = await run([SMBCmd.SHARESEC.value, share, action, args], check=False)
        if sharesec.returncode != 0:
            raise CallError(f'sharesec {action} failed with error: {sharesec.stderr.decode()}')
        return sharesec.stdout.decode()

    async def _delete(self, share):
        """
        Delete stored SD for share. This should be performed when share is
        deleted.
        If share_info.tdb lacks an entry for the share, sharesec --delete
        will return -1 and NT_STATUS_NOT_FOUND. In this case, exception should not
        be raised.
        """
        try:
            await self._sharesec(action='--delete', share=share)
        except Exception as e:
            if 'NT_STATUS_NOT_FOUND' not in str(e):
                raise CallError(e)

    async def _view_all(self, options=None):
        """
        Return Security Descriptor for all shares.
        """
        share_sd_list = []
        idx = 1
        share_entries = (await self._sharesec(action='--view-all')).split('\n\n')
        for share in share_entries:
            parsed_sd = await self.parse_share_sd(share, options)
            if parsed_sd:
                parsed_sd.update({'id': idx})
                idx = idx + 1
                share_sd_list.append(parsed_sd)

        return share_sd_list

    @accepts(
        Str('share_name'),
        Dict(
            'options',
            Bool('resolve_sids', default=True)
        )
    )
    async def getacl(self, share_name, options):
        """
        View the ACL information for `share_name`. The share ACL is distinct from filesystem
        ACLs which can be viewed by calling `filesystem.getacl`. `ae_who_name` will appear
        as `None` if the SMB service is stopped or if winbind is unable  to resolve the SID
        to a name.

        If the `option` `resolve_sids` is set to `False` then the returned ACL will not
        contain names.
        """
        sharesec = await self._sharesec(action='--view', share=share_name)
        share_sd = f'[{share_name.upper()}]\n{sharesec}'
        return await self.parse_share_sd(share_sd, options)

    async def _ae_to_string(self, ae):
        """
        Convert aclentry in Securty Descriptor dictionary to string
        representation used by sharesec.
        """
        if not ae['ae_who_sid'] and not ae['ae_who_name']:
            raise CallError('ACL Entry must have ae_who_sid or ae_who_name.', errno.EINVAL)

        if not ae['ae_who_sid']:
            name = f'{ae["ae_who_name"]["domain"]}\\{ae["ae_who_name"]["name"]}'
            wbinfo = await run([SMBCmd.WBINFO.value, '--name-to-sid', name], check=False)
            if wbinfo.returncode != 0:
                raise CallError(f'SID lookup for {name} failed: {wbinfo.stderr.decode()}')
            ae['ae_who_sid'] = (wbinfo.stdout.decode().split())[0]

        return f'{ae["ae_who_sid"]}:{ae["ae_type"]}/0x0/{ae["ae_perm"]}'

    async def _string_to_ae(self, perm_str):
        """
        Convert string representation of SD into dictionary.
        """
        return (RE_SHAREACLENTRY.match(f'ACL:{perm_str}')).groupdict()

    @private
    async def setacl(self, data, db_commit=True):
        """
        Set an ACL on `share_name`. Changes are written to samba's share_info.tdb file.
        This only impacts SMB sessions. Either ae_who_sid or ae_who_name must be specified
        for each ACL entry in the `share_acl`. If both are specified, then ae_who_sid will be used.
        The SMB service must be started in order to convert ae_who_name to a SID if those are
        used.

        `share_name` the name of the share

        `share_acl` a list of ACL entries (dictionaries) with the following keys:

        `ae_who_sid` who the ACL entry applies to expressed as a Windows SID

        `ae_who_name` who the ACL entry applies to expressed as a name. `ae_who_name` must
        be prefixed with the domain that the user is a member of. Local users will have the
        netbios name of the SMB server as a prefix. Example `freenas\\smbusers`

        `ae_perm` string representation of the permissions granted to the user or group.
        `FULL` grants read, write, execute, delete, write acl, and change owner.
        `CHANGE` grants read, write, execute, and delete.
        `READ` grants read and execute.

        `ae_type` can be ALLOWED or DENIED.
        """
        ae_list = []
        for entry in data['share_acl']:
            ae_list.append(await self._ae_to_string(entry))

        await self._sharesec(share=data['share_name'], action='--replace', args=','.join(ae_list))
        if not db_commit:
            return

        config_share = await self.middleware.call('sharing.smb.query', [('name', '=', data['share_name'])], {'get': True})
        await self.middleware.call('datastore.update', 'sharing.cifs_share', config_share['id'],
                                   {'cifs_share_acl': ' '.join(ae_list)})

    async def _flush_share_info(self):
        """
        Write stored share acls to share_info.tdb. This should only be called
        if share_info.tdb contains default entries.
        """
        shares = await self.middleware.call('datastore.query', 'sharing.cifs_share', [], {'prefix': 'cifs_'})
        for share in shares:
            if share['share_acl']:
                await self._sharesec(
                    share=share['name'],
                    action='--replace',
                    args=','.join(share['share_acl'].split())
                )

    @periodic(3600, run_on_start=False)
    @private
    async def check_share_info_tdb(self):
        """
        Use cached mtime value for share_info.tdb to determine whether
        to sync it up with what is stored in the freenas configuration file.
        Samba will run normally if share_info.tdb does not exist (it will automatically
        generate entries granting full control to world in this case). In this situation,
        immediately call _flush_share_info.
        """
        old_mtime = 0
        statedir = await self.middleware.call('smb.getparm', 'state directory', 'global')
        shareinfo = f'{statedir}/share_info.tdb'
        if not os.path.exists(shareinfo):
            if not await self.middleware.call('service.started', 'cifs'):
                return
            else:
                await self._flush_share_info()
                return

        if await self.middleware.call('cache.has_key', 'SHAREINFO_MTIME'):
            old_mtime = await self.middleware.call('cache.get', 'SHAREINFO_MTIME')

        if old_mtime == (os.stat(shareinfo)).st_mtime:
            return

        await self.middleware.call('smb.sharesec.synchronize_acls')
        await self.middleware.call('cache.put', 'SHAREINFO_MTIME', (os.stat(shareinfo)).st_mtime)

    @accepts()
    async def synchronize_acls(self):
        """
        Synchronize the share ACL stored in the config database with Samba's running
        configuration as reflected in the share_info.tdb file.

        The only situation in which the configuration stored in the database will
        overwrite samba's running configuration is if share_info.tdb is empty. Samba
        fakes a single S-1-1-0:ALLOW/0x0/FULL entry in the absence of an entry for a
        share in share_info.tdb.
        """
        rc = await self.middleware.call('smb.sharesec._view_all', {'resolve_sids': False})
        write_share_info = True

        for i in rc:
            if len(i['share_acl']) > 1:
                write_share_info = False
                break

            if i['share_acl'][0]['ae_who_sid'] != 'S-1-1-0' or i['share_acl'][0]['ae_perm'] != 'FULL':
                write_share_info = False
                break

        if write_share_info:
            return await self._flush_share_info()

        shares = await self.middleware.call('datastore.query', 'sharing.cifs_share', [], {'prefix': 'cifs_'})
        for s in shares:
            rc_info = (list(filter(lambda x: s['name'] == x['share_name'], rc)))[0]
            rc_acl = ' '.join([(await self._ae_to_string(i)) for i in rc_info['share_acl']])
            if rc_acl != s['share_acl']:
                self.logger.debug('updating stored ACL on %s to %s', s['name'], rc_acl)
                await self.middleware.call(
                    'datastore.update',
                    'sharing.cifs_share',
                    s['id'],
                    {'cifs_share_acl': rc_acl}
                )

    @filterable
    async def query(self, filters, options):
        """
        Use query-filters to search the SMB share ACLs present on server.
        """
        share_acls = await self._view_all({'resolve_sids': True})
        ret = filter_list(share_acls, filters, options)
        return ret

    @accepts(Dict(
        'smbsharesec_create',
        Str('share_name', required=True),
        List(
            'share_acl',
            items=[
                Dict(
                    'aclentry',
                    Str('ae_who_sid', default=None),
                    Dict(
                        'ae_who_name',
                        Str('domain', default=''),
                        Str('name', default=''),
                        default=None
                    ),
                    Str('ae_perm', enum=['FULL', 'CHANGE', 'READ']),
                    Str('ae_type', enum=['ALLOWED', 'DENIED'])
                )
            ],
            default=[{'ae_who_sid': 'S-1-1-0', 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'}])
    ))
    async def do_create(self, data):
        """
        Update the ACL on a given SMB share. Will write changes to both
        /var/db/system/samba4/share_info.tdb and the configuration file.
        Since an SMB share will _always_ have an ACL present, there is little
        distinction between the `create` and `update` methods apart from arguments.

        `share_name` - name of SMB share.

        `share_acl` a list of ACL entries (dictionaries) with the following keys:

        `ae_who_sid` who the ACL entry applies to expressed as a Windows SID

        `ae_who_name` who the ACL entry applies to expressed as a name. `ae_who_name` is
        a dictionary containing the following keys: `domain` that the user is a member of,
        `name` username in the domain. The domain for local users is the netbios name of
        the FreeNAS server.

        `ae_perm` string representation of the permissions granted to the user or group.
        `FULL` grants read, write, execute, delete, write acl, and change owner.
        `CHANGE` grants read, write, execute, and delete.
        `READ` grants read and execute.

        `ae_type` can be ALLOWED or DENIED.
        """
        await self.setacl(data)

    @accepts(
        Int('id', required=True),
        Dict(
            'smbsharesec_update',
            List(
                'share_acl',
                items=[
                    Dict(
                        'aclentry',
                        Str('ae_who_sid', default=None),
                        Dict(
                            'ae_who_name',
                            Str('domain', default=''),
                            Str('name', default=''),
                            default=None
                        ),
                        Str('ae_perm', enum=['FULL', 'CHANGE', 'READ']),
                        Str('ae_type', enum=['ALLOWED', 'DENIED']))
                ],
                default=[{'ae_who_sid': 'S-1-1-0', 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'}]
            )
        )
    )
    async def do_update(self, id, data):
        """
        Update the ACL on the share specified by the numerical index `id`. Will write changes
        to both /var/db/system/samba4/share_info.tdb and the configuration file.
        """
        old_acl = await self._get_instance(id)
        await self.setacl({"share_name": old_acl["share_name"], "share_acl": data["share_acl"]})
        return await self.getacl(old_acl["share_name"])

    @accepts(Str('id_or_name', required=True))
    async def do_delete(self, id_or_name):
        """
        Replace share ACL for the specified SMB share with the samba default ACL of S-1-1-0/FULL
        (Everyone - Full Control). In this case, access will be fully determined
        by the underlying filesystem ACLs and smb4.conf parameters governing access control
        and permissions.
        Share can be deleted by name or numerical by numerical index.
        """
        new_acl = {'share_acl': [
            {'ae_who_sid': 'S-1-1-0', 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'}
        ]}
        if not id_or_name.isdigit():
            old_acl = await self.getacl(id_or_name)
            new_acl.update({'share_name': id_or_name})
        else:
            old_acl = await self._get_instance(int(id_or_name))
            new_acl.update({'share_name': old_acl['share_name']})

        await self.setacl(new_acl)
        return old_acl
