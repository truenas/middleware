from middlewared.api.current import UserEntry
from middlewared.service import filterable_api_method, Service, job, private
from middlewared.utils.sid import get_domain_rid
from .util_account_policy import sync_account_policy
from .util_passdb import (
    add_version_info,
    delete_passdb_entry,
    insert_passdb_entries,
    query_passdb_entries,
    reinit_passdb,
    update_passdb_entry,
    user_entry_to_passdb_entry,
    PassdbMustReinit
)


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @filterable_api_method(private=True)
    def passdb_list(self, filters, options):
        """ query existing passdb users """
        clustered = self.middleware.call_sync('datastore.config', 'services.cifs')['cifs_srv_stateful_failover']
        try:
            return query_passdb_entries(filters or [], options or {}, clustered)
        except PassdbMustReinit as err:
            self.logger.warning(err.errmsg)
            self.synchronize_passdb().wait_sync(raise_error=True)
            return query_passdb_entries(filters or [], options or {}, clustered)

    @private
    def update_passdb_user(self, user: UserEntry):
        smb_config = self.middleware.call_sync('smb.config')
        server_name = smb_config['netbiosname']
        clustered = smb_config['stateful_failover']

        existing_entry = self.passdb_list([['username', '=', user['username']]])
        passdb_entry = user_entry_to_passdb_entry(
            server_name,
            user,
            existing_entry[0] if existing_entry else None,
        )

        update_passdb_entry(passdb_entry, clustered)

    @private
    def remove_passdb_user(self, username, sid):
        clustered = self.middleware.call_sync('datastore.config', 'services.cifs')['cifs_srv_stateful_failover']
        delete_passdb_entry(username, get_domain_rid(sid), clustered)

    @private
    def apply_account_policy(self):
        security = self.middleware.call_sync('system.security.config')
        sync_account_policy(security)

    @private
    @job(lock="passdb_sync", lock_queue_size=1)
    def synchronize_passdb(self, passdb_job):
        """ Sync user configuration from our user table with Samba's passdb.tdb file

        Params:
            force - force resync by deleting the existing passdb.tdb file

        Raises:
            PassdbMustReinit - the synchronize job must be rerun with force command
            RuntimeError - TDB library error
        """
        smb_config = self.middleware.call_sync('smb.config')
        server_name = smb_config['netbiosname']
        clustered = smb_config['stateful_failover']

        try:
            pdb_entries = {entry['user_rid']: entry for entry in query_passdb_entries([], {}, clustered)}
        except PassdbMustReinit:
            reinit_passdb(clustered)
            pdb_entries = {}

        add_version_info(clustered)
        to_update = []
        broken_entries = []

        for entry in self.middleware.call_sync('user.query', [("smb", "=", True), ('local', '=', True)]):
            existing_entry = pdb_entries.pop(get_domain_rid(entry['sid']), None)
            try:
                to_update.append(user_entry_to_passdb_entry(server_name, entry, existing_entry))
            except ValueError:
                # This will occur if config was restored without a secret seed
                broken_entries.append(entry['username'])
                continue

            if existing_entry and existing_entry['username'] != entry['username']:
                # username changed. Since it's part of key for one of tdb entries we have to nuke it.
                delete_passdb_entry(existing_entry['username'], existing_entry['user_rid'], clustered)

        # inserting over existing entries replaces them
        # this is performed with a transaction lock in place and so
        # we don't have to worry about rollback in case of failure
        insert_passdb_entries(to_update, clustered)

        for entry in pdb_entries.values():
            # we popped off keys as we matched them to existing DB users.
            # any remaining shouldn't be in the passdb file

            self.logger.debug('%s: removing user from SMB user database', entry['username'])
            delete_passdb_entry(entry['username'], entry['user_rid'], clustered)

        if broken_entries:
            self.middleware.call_sync("alert.oneshot_create", "SMBUserMissingHash",
                                      {'entries': ','.join(broken_entries)})
        else:
            self.middleware.call_sync("alert.oneshot_delete", "SMBUserMissingHash")
