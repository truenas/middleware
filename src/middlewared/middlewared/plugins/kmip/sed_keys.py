from middlewared.service import job, private, Service

from .connection import KMIPServerMixin


'''
SED keys are stored in 2 places:
1) system.advanced table
2) storage.disk table

There are 3 possible cases which we need to handle for storage.disk
1) A disk row can have SED key
2) A disk row can have a blank SED key
3) A disk row can be removed

There are 2 possible cases which we need to handle for system.advanced
1) system.advanced.config can have global SED password
2) system.advanced.config cannot have global SED password
'''


class KMIPService(Service, KMIPServerMixin):

    def __init__(self, *args, **kwargs):
        """
        System will never directly query KMIP server to determine the SED keys when it actually uses the SED keys.
        Instead when middleware boots, we will cache keys and maintain a record of them in memory which the system
        will use and rely on for SED related tasks.
        """
        super().__init__(*args, **kwargs)
        self.disks_keys = {}
        self.global_sed_key = ''

    @private
    async def sed_keys_pending_sync(self):
        """
        We determine if we have SED keys pending sync by verifying following scenarios:

        1) kmip.config.enabled and kmip.config.manage_sed_disks are set - which means we have to push all SED keys
           from storage.disk and system.advanced to KMIP server
        2) kmip.config.enabled or kmip.config.manage_sed_disks is unset ( any one of them ) - which means we have to
           pull SED keys from the KMIP server for the relevant rows

        How the flow is designed to work for storage.disk when a key is added is following:
        1) User adds password for disk
        2) Password is saved in database
        3) If KMIP service is enabled, kmip sync is initiated for SED keys
        4) For the disk in question, value of password in database is given priority and pushed to the KMIP server
        5) If KMIP uid field is already set for the disk in question, system is going to remove that key and push the
           new password to the KMIP server.
        6) Once the key has been pushed successfully, it is removed from the database and added to memory for fast
           retrieval.

        For above case, we determine that a key needs to be synced based on the fact that KMIP sync is enabled for
        SED keys and we have sed key saved in database.

        Flow when key is removed for storage.disk:
        1) User sets empty value for the password
        2) It is saved in database
        3) If the key had been saved already to KMIP server, it is removed and also it
           is removed from the memory.
        4) Difference from above case is that a sync is not initiated in this case and on key
           removal from database, KMIP uid is revoked/removed at the same time.

        For the above case, we don't get to a state where we can have pending sync as database is updated instantly
        removing kmip uid and flushing password.

        When a disk is removed, the same steps as above are carried out.

        Above cases took into account when KMIP sync was enabled, when KMIP sync is disabled for SED keys,
        following steps are performed to determine if we have kmip sync pending for SED keys.

        Flow when KMIP sync is disabled for SED keys:
        1) KMIP server is contacted for disks which have kmip uid field set.
        2) Key is retrieved and updated for the disk in question.
        3) If KMIP server could not be contacted, we have sync pending for the disks in question then.
        4) Meanwhile if the user sets a new password for the disks, that password will be given precedence over
           the key saved in KMIP Server and it will be removed as soon as KMIP server can be contacted.

        For the above case, sync is declared pending if kmip uid field has a uid present.

        The same steps are followed for system.advanced except for the one where we remove disks which is not
        true for system.advanced.

        During this, we also declare sync is pending if we have SED sync enabled and the keys
        are not in the memory as that is what we rely on while actually using the SED keys functionality.
        """
        adv_config = await self.middleware.call('datastore.config', 'system.advanced', {'prefix': 'adv_'})
        disks = await self.middleware.call('datastore.query', 'storage.disk', [], {'prefix': 'disk_'})
        config = await self.middleware.call('kmip.config')
        check_db_key = config['enabled'] and config['manage_sed_disks']
        for disk in disks:
            if check_db_key and (disk['passwd'] or (disk['kmip_uid'] and disk['identifier'] not in self.disks_keys)):
                return True
            elif not check_db_key and disk['kmip_uid']:
                return True
        if check_db_key and (adv_config['sed_passwd'] or (not self.global_sed_key and adv_config['kmip_uid'])):
            return True
        elif not check_db_key and adv_config['kmip_uid']:
            return True
        return False

    @private
    def push_sed_keys(self, ids=None):
        """
        When push SED keys is initiated, we carry out following steps:

        1) For any disk which has it's key stored in KMIP server and not in database, we first update memory
           cache to reflect the key present in the KMIP server.
        2) If the disk in question does not have a SED key and no kmip uid, we don't have a key set for it and we
           dismiss that disk.
        3) For point (1), the key has already been pushed to the KMIP server so we don't need to do that again.
        4) Moving on, we are left with the case where we have SED key stored in database for disk with/without a
           kmip uid present in the disk row.
        5) If kmip uid present for the disk in question, we first revoke/remove it.
        6) Existing SED key present in the database is pushed to the KMIP Server and database is updated
           with new kmip uid.

        The same steps are followed for system.advanced.
        """
        adv_config = self.middleware.call_sync('datastore.config', 'system.advanced', {'prefix': 'adv_'})
        failed = []
        with self._connection(self.middleware.call_sync('kmip.connection_config')) as conn:
            for disk in self.middleware.call_sync(
                'datastore.query', 'storage.disk', [['identifier', 'in', ids]] if ids else [], {'prefix': 'disk_'}
            ):
                if not disk['passwd'] and disk['kmip_uid']:
                    try:
                        key = self._retrieve_secret_data(disk['kmip_uid'], conn)
                    except Exception as e:
                        self.middleware.logger.debug(f'Failed to retrieve key for {disk["identifier"]}: {e}')
                    else:
                        self.disks_keys[disk['identifier']] = key
                    continue
                elif not disk['passwd']:
                    continue

                self.disks_keys[disk['identifier']] = disk['passwd']
                destroy_successful = False
                if disk['kmip_uid']:
                    # This needs to be revoked and destroyed
                    destroy_successful = self._revoke_and_destroy_key(
                        disk['kmip_uid'], conn, self.middleware.logger, disk['identifier']
                    )
                try:
                    uid = self._register_secret_data(disk['identifier'], self.disks_keys[disk['identifier']], conn)
                except Exception:
                    failed.append(disk['identifier'])
                    update_data = {'kmip_uid': None} if destroy_successful else {}
                else:
                    update_data = {'passwd': '', 'kmip_uid': uid}
                if update_data:
                    self.middleware.call_sync(
                        'datastore.update', 'storage.disk', disk['identifier'], update_data, {'prefix': 'disk_'}
                    )
            if not adv_config['sed_passwd'] and adv_config['kmip_uid']:
                try:
                    key = self._retrieve_secret_data(adv_config['kmip_uid'], conn)
                except Exception:
                    failed.append('Global SED Key')
                else:
                    self.global_sed_key = key
            elif adv_config['sed_passwd']:
                if adv_config['kmip_uid']:
                    self._revoke_and_destroy_key(
                        adv_config['kmip_uid'], conn, self.middleware.logger, 'SED Global Password'
                    )
                    self.middleware.call_sync(
                        'datastore.update', 'system.advanced', adv_config['id'], {'adv_kmip_uid': None}
                    )
                self.global_sed_key = adv_config['sed_passwd']
                try:
                    uid = self._register_secret_data('global_sed_key', self.global_sed_key, conn)
                except Exception:
                    failed.append('Global SED Key')
                else:
                    self.middleware.call_sync(
                        'datastore.update', 'system.advanced',
                        adv_config['id'], {'adv_sed_passwd': '', 'adv_kmip_uid': uid}
                    )
        return failed

    @private
    def pull_sed_keys(self):
        """
        We pull SED keys from the KMIP server when SED sync has been disabled. In this case, following steps
        are executed:

        1) If a disk has a SED key saved in database, that is given preference over the key saved in the KMIP server.
           Which in this case kmip uid is simply removed and database is updated to reflect that.
        2) If a disk does not have a SED key saved in the database, we first check if we have the key saved
           in memory cache and use that to update the database and remove the kmip uid from the database.
        3) If memory cache also does not have the SED key, we finally try to retrieve the key from the KMIP server
           and if we succeed, we update the database to reflect that.

        The same steps are carried out for system.advanced.
        """
        failed = []
        connection_successful = self.middleware.call_sync('kmip.test_connection')
        for disk in self.middleware.call_sync(
            'datastore.query', 'storage.disk', [['kmip_uid', '!=', None]], {'prefix': 'disk_'}
        ):
            try:
                if disk['passwd']:
                    key = disk['passwd']
                elif self.disks_keys.get(disk['identifier']):
                    key = self.disks_keys[disk['identifier']]
                elif connection_successful:
                    with self._connection(self.middleware.call_sync('kmip.connection_config')) as conn:
                        key = self._retrieve_secret_data(disk['kmip_uid'], conn)
                else:
                    raise Exception('Failed to sync disk')
            except Exception:
                failed.append(disk['identifier'])
            else:
                update_data = {'passwd': key, 'kmip_uid': None}
                self.middleware.call_sync(
                    'datastore.update', 'storage.disk', disk['identifier'], update_data, {'prefix': 'disk_'}
                )
                self.disks_keys.pop(disk['identifier'], None)
                if connection_successful:
                    self.middleware.call_sync('kmip.delete_kmip_secret_data', disk['kmip_uid'])
        adv_config = self.middleware.call_sync('datastore.config', 'system.advanced', {'prefix': 'adv_'})
        if adv_config['kmip_uid']:
            key = None
            if adv_config['sed_passwd']:
                key = adv_config['sed_passwd']
            elif self.global_sed_key:
                key = self.global_sed_key
            elif connection_successful:
                try:
                    with self._connection(self.middleware.call_sync('kmip.connection_config')) as conn:
                        key = self._retrieve_secret_data(adv_config['kmip_uid'], conn)
                except Exception:
                    failed.append('Global SED Key')
            if key:
                self.middleware.call_sync(
                    'datastore.update', 'system.advanced',
                    adv_config['id'], {
                        'adv_sed_passwd': key, 'adv_kmip_uid': None
                    }
                )
                self.global_sed_key = ''
                if connection_successful:
                    self.middleware.call_sync('kmip.delete_kmip_secret_data', adv_config['kmip_uid'])
        return failed

    @job(lock=lambda args: f'kmip_sync_sed_keys_{args}')
    @private
    def sync_sed_keys(self, job, ids=None):
        """
        SED keys are synced if we have sync pending for SED keys. If SED sync is enabled with KMIP, we push
        SED keys, else we pull SED keys and update the database in both cases.
        """
        if not self.middleware.call_sync('kmip.sed_keys_pending_sync'):
            return
        config = self.middleware.call_sync('kmip.config')
        conn_successful = self.middleware.call_sync('kmip.test_connection', None, True)
        if config['enabled'] and config['manage_sed_disks']:
            if conn_successful:
                failed = self.push_sed_keys(ids)
            else:
                return
        else:
            failed = self.pull_sed_keys()
        ret_failed = failed.copy()
        try:
            failed.remove('Global SED Key')
        except ValueError:
            pass
        else:
            self.middleware.call_sync('alert.oneshot_create', 'KMIPSEDGlobalPasswordSyncFailure')
        finally:
            if failed:
                self.middleware.call_sync(
                    'alert.oneshot_create', 'KMIPSEDDisksSyncFailure', {'disks': ','.join(failed)}
                )
        self.middleware.call_hook_sync('kmip.sed_keys_sync')
        return ret_failed

    @private
    async def clear_sync_pending_sed_keys(self):
        """
        We expose an option to clear keys which are pending kmip sync, this can be done if the user knows for certain
        that the KMIP server can never be reached now and he/she does not want the system trying again to initiate
        a sync with the KMIP server.
        """
        for disk in await self.middleware.call(
            'datastore.query', 'storage.disk', [['kmip_uid', '!=', None]], {'prefix': 'disk_'}
        ):
            await self.middleware.call(
                'datastore.update', 'storage.disk', disk['identifier'], {'disk_kmip_uid': None}
            )
        adv_config = await self.middleware.call('datastore.config', 'system.advanced', {'prefix': 'adv_'})
        if adv_config['kmip_uid']:
            await self.middleware.call(
                'datastore.update', 'system.advanced', adv_config['id'], {'adv_kmip_uid': None}
            )
        self.global_sed_key = ''
        self.disks_keys = {}

    @private
    def initialize_sed_keys(self, connection_success):
        """
        On middleware boot, we initialize memory cache to contain all the SED keys which we can later use
        for SED related functionality.
        """
        for disk in self.middleware.call_sync(
            'datastore.query', 'storage.disk', [], {'prefix': 'disk_'}
        ):
            if disk['passwd']:
                self.disks_keys[disk['identifier']] = disk['passwd']
            elif disk['kmip_uid'] and connection_success:
                try:
                    with self._connection(self.middleware.call_sync('kmip.connection_config')) as conn:
                        key = self._retrieve_secret_data(disk['kmip_uid'], conn)
                except Exception:
                    self.middleware.logger.debug(f'Failed to retrieve SED disk key for {disk["identifier"]}')
                else:
                    self.disks_keys[disk['identifier']] = key
        adv_config = self.middleware.call_sync('datastore.config', 'system.advanced', {'prefix': 'adv_'})
        if adv_config['sed_passwd']:
            self.global_sed_key = adv_config['sed_passwd']
        elif connection_success and adv_config['kmip_uid']:
            try:
                with self._connection(self.middleware.call_sync('kmip.connection_config')) as conn:
                    key = self._retrieve_secret_data(adv_config['kmip_uid'], conn)
            except Exception:
                self.middleware.logger.debug(f'Failed to retrieve global SED key')
            else:
                self.global_sed_key = key

    @private
    async def update_sed_keys(self, data):
        if 'global_password' in data:
            self.global_sed_key = data['global_password']
        if 'sed_disks_keys' in data:
            self.disks_keys = data['sed_disks_keys']

    @private
    async def sed_keys(self):
        return {
            'global_password': await self.sed_global_password(),
            'sed_disks_keys': await self.retrieve_sed_disks_keys(),
        }

    @private
    async def sed_global_password(self):
        return self.global_sed_key

    @private
    async def reset_sed_global_password(self, kmip_uid):
        self.global_sed_key = ''
        if kmip_uid:
            try:
                await self.middleware.call('kmip.delete_kmip_secret_data', kmip_uid)
            except Exception as e:
                self.middleware.logger.debug(
                    f'Failed to remove password from KMIP server for SED Global key: {e}'
                )

    @private
    async def reset_sed_disk_password(self, disk_id, kmip_uid):
        self.disks_keys.pop(disk_id, None)
        if kmip_uid:
            try:
                await self.middleware.call('kmip.delete_kmip_secret_data', kmip_uid)
            except Exception as e:
                self.middleware.logger.debug(
                    f'Failed to remove password from KMIP server for {disk_id}: {e}'
                )
        await self.middleware.call_hook('kmip.sed_keys_sync')

    @private
    async def retrieve_sed_disks_keys(self):
        return self.disks_keys
