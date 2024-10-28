import os

from middlewared.api.current import UserEntry
from middlewared.service import filterable_api_method, Service, job, private
from middlewared.utils.sid import get_domain_rid
from .util_passdb import (
    delete_passdb_entry,
    insert_passdb_entries,
    query_passdb_entries,
    update_passdb_entry,
    user_entry_to_passdb_entry,
    PassdbMustReinit,
    PASSDB_PATH
)


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @filterable_api_method
    def passdb_list(self, filters, options):
        """ query existing passdb users """
        try:
            return query_passdb_entries(filters or [], options or {})
        except PassdbMustReinit as err:
            self.logger.warning(err.errmsg)
            self.synchronize_passdb(True).wait_sync(raise_error=True)
            return query_passdb_entries(filters or [], options or {})

    @private
    def update_passdb_user(self, user: UserEntry):
        server_name = self.middleware.call_sync('smb.config')['netbiosname_local']

        existing_entry = self.passdb_list([['username', '=', user['username']]])
        passdb_entry = user_entry_to_passdb_entry(
            server_name,
            user,
            existing_entry[0] if existing_entry else None
        )

        update_passdb_entry(passdb_entry)

    @private
    def remove_passdb_user(self, username, sid):
        delete_passdb_entry(username, get_domain_rid(sid))

    @private
    @job(lock="passdb_sync", lock_queue_size=1)
    def synchronize_passdb(self, job, force=False):
        """ Sync user configuration from our user table with Samba's passdb.tdb file

        Params:
            force - force resync by deleting the existing passdb.tdb file

        Raises:
            PassdbMustReinit - the synchronize job must be rerun with force command
            RuntimeError - TDB library error
        """
        server_name = self.middleware.call_sync('smb.config')['netbiosname_local']
        if force:
            try:
                os.unlink(PASSDB_PATH)
            except FileNotFoundError:
                pass

        pdb_entries = {entry['user_rid']: entry for entry in query_passdb_entries([], {})}
        to_update = []

        for entry in self.middleware.call_sync('user.query', [("smb", "=", True), ('local', '=', True)]):
            existing_entry = pdb_entries.pop(get_domain_rid(entry['sid']), None)
            to_update.append(user_entry_to_passdb_entry(server_name, entry, existing_entry))

            if existing_entry and existing_entry['username'] != entry['username']:
                # username changed. Since it's part of key for one of tdb entries we have to nuke it.
                delete_passdb_entry(existing_entry['username'], existing_entry['user_rid'])

        # inserting over existing entries replaces them
        # this is performed with a transaction lock in place and so
        # we don't have to worry about rollback in case of failure
        insert_passdb_entries(to_update)

        for entry in pdb_entries.values():
            # we popped off keys as we matched them to existing DB users.
            # any remaining shouldn't be in the passdb file

            self.logger.debug('%s: removing user from SMB user database', entry['username'])
            delete_passdb_entry(entry['username'], entry['user_rid'])
