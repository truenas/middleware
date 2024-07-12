import os
import tdb
import struct

from middlewared.service import Service, job, private
from middlewared.service_exception import CallError
from middlewared.utils.sid import (
    db_id_to_rid,
    get_domain_rid,
    lsa_sidtype,
    sid_is_valid,
    BASE_RID_USER,
    DomainRid
)
from middlewared.utils.tdb import (
    get_tdb_handle,
    TDBDataType,
    TDBPathType,
    TDBOptions,
)
from middlewared.plugins.idmap_.idmap_constants import IDType
from middlewared.plugins.smb_.constants import SMBBuiltin, SMBPath
from middlewared.plugins.smb_.util_groupmap import (
    delete_groupmap_entry,
    insert_groupmap_entries,
    list_foreign_group_memberships,
    query_groupmap_entries,
    GroupmapFile,
    GroupmapEntryType,
    SMBGroupMap,
    SMBGroupMembership,
)

WINBINDD_AUTO_ALLOCATED = ('S-1-5-32-544', 'S-1-5-32-545', 'S-1-5-32-546')
WINBINDD_WELL_KNOWN_PADDING = 100

WINBIND_IDMAP_CACHE = f'{SMBPath.CACHE_DIR.platform()}/winbindd_cache.tdb'
WINBIND_IDMAP_TDB_OPTIONS = TDBOptions(TDBPathType.CUSTOM, TDBDataType.BYTES)


def clear_winbind_idmap_cache():
    with get_tdb_handle(WINBIND_IDMAP_CACHE, WINBIND_IDMAP_TDB_OPTIONS) as hdl:
        return hdl.clear()


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @private
    def add_groupmap(self, group):
        server_sid = self.middleware.call_sync('smb.local_server_sid')
        rid = db_id_to_rid(IDType.GROUP, group['id'])
        entry = SMBGroupMap(
            sid=f'{server_sid}-{rid}',
            gid=group['gid'],
            sid_type=lsa_sidtype.ALIAS,
            name=group['group'],
            comment=''
        )
        insert_groupmap_entries(GroupmapFile.DEFAULT, [entry])

    @private
    def del_groupmap(self, db_id):
        server_sid = self.middleware.call_sync('smb.local_server_sid')
        rid = db_id_to_rid(IDType.GROUP, db_id)
        delete_groupmap_entry(
            GroupmapFile.DEFAULT,
            GroupmapEntryType.GROUP_MAPPING,
            entry_sid=f'{server_sid}-{rid}',
        )

    @private
    def sync_foreign_groups(self):
        """
        Domain Users, and Domain Admins must have S-1-5-32-545 and S-1-5-32-544
        added to their respective Unix tokens for correct behavior in AD domain.
        These are added by making them foreign members in the group_mapping for
        the repsective alias. This membership is generated during samba startup
        when newly creating these groups (if they don't exist), but can get
        lost, resulting in unexpected / erratic permissions behavior.
        """
        # fresh groupmap listing is to ensure we have accurate / current info.
        groupmap = self.groupmap_list()
        localsid = groupmap['localsid']

        entries = [
            SMBGroupMembership(
                sid=f'{localsid}-{DomainRid.ADMINS}',
                groups=(SMBBuiltin.ADMINISTRATORS.sid,)
            ),
            SMBGroupMembership(
                sid=f'{localsid}-{DomainRid.GUESTS}',
                groups=(SMBBuiltin.GUESTS.sid,)
            ),
            SMBGroupMembership(
                sid=groupmap['local'][SMBBuiltin.USERS.rid]['sid'],
                groups=(SMBBuiltin.USERS.sid,)
            ),
        ]

        # We keep separate list of what members we expect for these groups
        admins = [f'{localsid}-{DomainRid.ADMINS}']
        guests = [f'{localsid}-{DomainRid.GUESTS}']

        # Samba has special behavior if DomainRid.USERS is set for local domain
        # and so we map the builtin_users account to a normal sid then make it
        # a member of S-1-5-32-545
        users = [groupmap['local'][SMBBuiltin.USERS]['sid']]

        if (admin_group := self.middleware.call_sync('smb.config')['admin_group']):
            if (found := self.middleware.call_sync('group.query', [('group', '=', admin_group)])):
                entries.append(SMBGroupMembership(
                    sid=found[0]['sid'],
                    groups=(SMBBuiltin.ADMINISTRATORS.sid,)
                ))
                admins.append(found[0]['sid'])
            else:
                self.logger.warning('%s: SMB admin group does not exist', admin_group)

        ad_state = self.middleware.call_sync('activedirectory.get_state')
        if ad_state == 'HEALTHY':
            try:
                domain_info = self.middleware.call_sync('idmap.domain_info',
                                                        'DS_TYPE_ACTIVEDIRECTORY')
                domain_sid = domain_info['sid']
                # add domain account SIDS
                entries.append((SMBGroupMembership(
                    sid=f'{domain_sid}-{DomainRid.ADMINS}',
                    groups=(SMBBuiltin.ADMINISTRATORS.sid,)
                )))
                admins.append(f'{domain_sid}-{DomainRid.ADMINS}')
                entries.append((SMBGroupMembership(
                    sid=f'{domain_sid}-{DomainRid.USERS}',
                    groups=(SMBBuiltin.USERS.sid,)
                )))
                users.append(f'{domain_sid}-{DomainRid.USERS}')
                entries.append((SMBGroupMembership(
                    sid=f'{domain_sid}-{DomainRid.GUESTS}',
                    groups=(SMBBuiltin.GUESTS.sid,)
                )))
                guests.append(f'{domain_sid}-{DomainRid.GUESTS}')
            except Exception:
                self.logger.warning('Failed to retrieve idmap domain info', exc_info=True)

        insert_groupmap_entries(GroupmapFile.DEFAULT, entries)

        # double-check that we have expected memberships now and no extras
        unexpected_memberof_entries = query_groupmap_entries(GroupmapFile.DEFAULT, [
            ['entry_type', '=', GroupmapEntryType.MEMBERSHIP.name],
            ['sid', 'nin', admins + guests + users]
        ], {})

        for entry in unexpected_memberof_entries:
            self.logger.error(
                '%s: unexpected account present in group mapping configuration for groups '
                'with the following sids %s. This grants the account privileges beyond what '
                'would normally be granted by the backend in TrueNAS potentially indicating '
                'an underlying security issue. This mapping entry will be automatically '
                'removed to restore TrueNAS to its expected configuration.',
                entry['sid'], entry['groups']
            )

            try:
                delete_groupmap_entry(
                    GroupmapFile.DEFAULT,
                    GroupmapEntryType.MEMBERSHIP,
                    entry_sid=entry['sid'],
                )
            except Exception:
                self.logger.error('Failed to remove unexpected groupmap entry', exc_info=True)

    @private
    def initialize_idmap_tdb(self, low_range):
        tdb_path = f'{SMBPath.STATEDIR.platform()}/winbindd_idmap.tdb'
        tdb_flags = tdb.DEFAULT
        open_flags = os.O_CREAT | os.O_RDWR

        try:
            tdb_handle = tdb.Tdb(tdb_path, 0, tdb_flags, open_flags, 0o644)
        except Exception:
            self.logger.warning("Failed to create winbindd_idmap.tdb", exc_info=True)
            return None

        try:
            for key, val in [
                (b'IDMAP_VERSION\x00', 2),
                (b'USER HWM\x00', low_range),
                (b'GROUP HWM\x00', low_range)
            ]:
                tdb_handle.store(key, struct.pack("<L", val))
        except Exception:
            self.logger.warning('Failed to initialize winbindd_idmap.tdb', exc_info=True)
            tdb_handle.close()
            return None

        return tdb_handle

    @private
    def validate_groupmap_hwm(self, low_range):
        """
        Middleware forces allocation of GIDs for Users, Groups, and Administrators
        to be deterministic with the default idmap backend. Bump up the idmap_tdb
        high-water mark to avoid conflicts with these and remove any mappings that
        conflict. Winbindd will regenerate the removed ones as-needed.
        """
        def add_key(tdb_handle, gid, sid):
            gid_val = f'GID {gid}\x00'.encode()
            sid_val = f'{sid}\x00'.encode()
            tdb_handle.store(gid_val, sid_val)
            tdb_handle.store(sid_val, gid_val)

        def remove_key(tdb_handle, key, reverse):
            tdb_handle.delete(key)
            if reverse:
                tdb_handle.delete(reverse)

        must_reload = False
        len_wb_groups = len(WINBINDD_AUTO_ALLOCATED)
        builtins = self.middleware.call_sync('idmap.builtins')

        try:
            tdb_handle = tdb.open(f"{SMBPath.STATEDIR.platform()}/winbindd_idmap.tdb")
        except FileNotFoundError:
            tdb_handle = self.initialize_idmap_tdb(low_range)
            if not tdb_handle:
                return False

        try:
            tdb_handle.transaction_start()
            group_hwm_bytes = tdb_handle.get(b'GROUP HWM\00')
            hwm = struct.unpack("<L", group_hwm_bytes)[0]
            if hwm < low_range + len_wb_groups + len(builtins):
                hwm = low_range + len_wb_groups + len(builtins) + WINBINDD_WELL_KNOWN_PADDING
                new_hwm_bytes = struct.pack("<L", hwm)
                tdb_handle.store(b'GROUP HWM\00', new_hwm_bytes)
                must_reload = True

            for key in tdb_handle.keys():
                # sample key: b'GID 9000020\x00'
                if key[:3] == b'GID' and int(key.decode()[4:-1]) < (low_range + len_wb_groups):
                    reverse = tdb_handle.get(key)
                    remove_key(tdb_handle, key, reverse)
                    must_reload = True

            for entry in builtins:
                if not entry['set']:
                    continue

                sid_key = f'{entry["sid"]}\x00'.encode()
                val = tdb_handle.get(f'{entry["sid"]}\x00'.encode())
                if val is None or val.decode() != f'GID {entry["gid"]}\x00':
                    if sid_key in tdb_handle.keys():
                        self.logger.debug(
                            "incorrect sid mapping detected %s -> %s"
                            "replacing with %s -> %s",
                            entry['sid'], val.decode()[4:-1] if val else "None",
                            entry['sid'], entry['gid']
                        )
                        remove_key(tdb_handle, f'{entry["sid"]}\x00'.encode(), val)

                    add_key(tdb_handle, entry['gid'], entry['sid'])
                    must_reload = True

            tdb_handle.transaction_commit()

        except Exception as e:
            tdb_handle.transaction_cancel()
            self.logger.warning("TDB maintenace failed: %s", e)

        finally:
            tdb_handle.close()

        if must_reload:
            self.middleware.call_sync('idmap.snapshot_samba4_dataset')

        return must_reload

    @private
    def groupmap_list(self):
        """
        Separate out the groupmap output into builtins, locals, and invalid entries.
        Invalid entries are ones that aren't from our domain, or are mapped to gid -1.
        Latter occurs when group mapping is lost. In case of invalid entries, we store
        list of SIDS to be removed. SID is necessary and sufficient for groupmap removal.
        """
        rv = {"builtins": {}, "local": {}, "local_builtins": {}, "invalid": {}}

        localsid = self.middleware.call_sync('smb.local_server_sid')
        legacy_entries = []

        for g in query_groupmap_entries(GroupmapFile.DEFAULT, [
            ['entry_type', '=', GroupmapEntryType.GROUP_MAPPING.name]
        ], {}):
            gid = g['gid']
            key = 'invalid'
            if gid == -1:
                rv[key].append(g['sid'])
                continue

            if g['sid'].startswith("S-1-5-32"):
                key = 'builtins'
            elif g['sid'].startswith(localsid) and g['gid'] in (544, 546):
                key = 'local_builtins'
            elif g['sid'].startswith(localsid):
                if int(get_domain_rid(g['sid'])) < BASE_RID_USER:
                    legacy_entries.append(g)
                    continue

                key = 'local'

            if key == 'invalid' or rv[key].get(gid):
                rv['invalid'].append(g['sid'])
                continue

            rv[key][gid] = g

        rv['localsid'] = localsid

        for entry in legacy_entries:
            # keep copy of legacy groupmap entries so that we can rewrite our share_info.tdb file
            gm = SMBGroupMap(
                sid=entry['sid'],
                gid=entry['gid'],
                sid_type=lsa_sidtype.ALIAS,
                name=entry['name'],
                comment=entry['comment']
            )
            insert_groupmap_entries(GroupmapFile.REJECT, [gm])

            try:
                delete_groupmap_entry(
                    GroupmapFile.DEFAULT,
                    GroupmapEntryType.GROUP_MAPPING,
                    entry_sid=entry['sid'],
                )
            except Exception:
                self.logger.debug('Failed to delete legacy entry', exc_info=True)

        return rv

    @private
    def groupmap_listmem(self, sid):
        """
        This method returns a list of SIDS that are members of the specified SID.

        Samba's group mapping database can contain foreign group mappings for particular SID entries
        This provides nesting for groups, and SID membership is evaluated when samba overrides
        POSIX permissions for example when a user is a member of the S-1-5-32-544 (BUILTIN\\admininstrators)

        Per MS-DTYP certain well-known SIDs / rids must be members of certain builtin groups. For
        example, the administrators RID for a domain (remote and local) must be a member of S-1-5-32-544
        otherwise domain admins won't have DACL override privileges.
        """
        if not sid_is_valid(sid):
            raise ValueError(f'{sid}: not a valid SID')

        return list_foreign_group_memberships(GroupmapFile.DEFAULT, sid)

    @private
    def sync_builtins(self, to_add):
        """
        builtin groups are automatically allocated by winbindd / idmap_tdb. We want these
        mappings to be written deterministically so that if for some horrible reason an
        end-users decides to write these GIDs to an ACL entry it is consistent between
        TrueNAS servers and persistent across updates.
        """

        # Because the beginning range is determined by the range of IDs allocated for BUILTIN
        # users we have to request from the samba running configuration
        idmap_backend = self.middleware.call_sync("smb.getparm", "idmap config * : backend", "GLOBAL")
        idmap_range = self.middleware.call_sync("smb.getparm", "idmap config * : range", "GLOBAL")

        if idmap_backend != "tdb":
            """
            idmap_autorid and potentially other allocating idmap backends may be used for
            the default domain. We do not want to touch how these are allocated.
            """
            return False

        low_range = int(idmap_range.split("-")[0].strip())
        for b in (SMBBuiltin.ADMINISTRATORS, SMBBuiltin.USERS, SMBBuiltin.GUESTS):
            offset = b.rid - SMBBuiltin.ADMINISTRATORS.rid

            gid = low_range + offset
            to_add.append(SMBGroupMap(
                sid=b.sid,
                gid=gid,
                sid_type=lsa_sidtype.ALIAS,
                name=b.nt_name,
                comment=''
            ))

        return self.validate_groupmap_hwm(low_range)

    @private
    @job(lock="groupmap_sync", lock_queue_size=1)
    def synchronize_group_mappings(self, job, bypass_sentinel_check=False):
        """
        This method does the following:
        1) ensures that group_mapping.tdb has all required groupmap entries
        2) ensures that builtin SIDs S-1-5-32-544, S-1-5-32-545, and S-1-5-32-546
           exist and are deterministically mapped to expected GIDs
        3) ensures that all expected foreign aliases for builtin SIDs above exist.
        4) flush various caches if required.
        """
        entries = []
        if (status := self.middleware.call_sync('failover.status')) not in ('SINGLE', 'MASTER'):
            self.middleware.logger.debug('%s: skipping groupmap sync due to failover status', status)
            return

        if not bypass_sentinel_check and not self.middleware.call_sync('smb.is_configured'):
            raise CallError(
                "SMB server configuration is not complete. "
                "This may indicate system dataset setup failure."
            )

        groupmap = self.groupmap_list()

        groups = self.middleware.call_sync('group.query', [('local', '=', True), ('smb', '=', True)])
        groups.append(self.middleware.call_sync('group.query', [('gid', '=', 545), ('local', '=', True)], {'get': True}))
        gid_set = {x["gid"] for x in groups}

        for group in groups:
            entries.append(SMBGroupMap(
                sid=group['sid'],
                gid=group['gid'],
                sid_type=lsa_sidtype.ALIAS,
                name=group['group'],
                comment=''
            ))

        for entry in groupmap['local'].values():
            # delete entries that don't map to a local account
            if entry['gid'] in gid_set:
                continue

            try:
                delete_groupmap_entry(
                    GroupmapFile.DEFAULT,
                    GroupmapEntryType.GROUP_MAPPING,
                    sid=entry['sid'],
                )
            except Exception:
                self.logger.warning('%s: failed to remove group mapping', entry['sid'], exc_info=True)

        must_remove_cache = self.sync_builtins(entries)
        insert_groupmap_entries(GroupmapFile.DEFAULT, entries)

        self.sync_foreign_groups()

        if must_remove_cache:
            clear_winbind_idmap_cache()
            try:
                self.middleware.call_sync('idmap.gencache.flush')
            except Exception:
                self.logger.warning('Failed to flush caches after groupmap changes.', exc_info=True)
