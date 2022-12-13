import errno

from middlewared.schema import accepts, Bool, Dict, Int, List, OROperator, Ref, returns, Str, UnixPerm
from middlewared.service import CallError, item_method, job, Service, ValidationErrors
from middlewared.utils import filter_list


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @accepts(
        Str('id', required=True),
        Dict(
            'pool_dataset_permission',
            Str('user'),
            Str('group'),
            UnixPerm('mode', null=True),
            OROperator(
                Ref('nfs4_acl'),
                Ref('posix1e_acl'),
                name='acl'
            ),
            Dict(
                'options',
                Bool('set_default_acl', default=False),
                Bool('stripacl', default=False),
                Bool('recursive', default=False),
                Bool('traverse', default=False),
            ),
            register=True,
        ),
    )
    @returns(Ref('pool_dataset_permission'))
    @item_method
    @job(lock="dataset_permission_change")
    async def permission(self, job, id, data):
        """
        Set permissions for a dataset `id`. Permissions may be specified as
        either a posix `mode` or an `acl`. This method is a wrapper around
        `filesystem.setperm`, `filesystem.setacl`, and `filesystem.chown`

        `filesystem.setperm` is called if `mode` is specified.
        `filesystem.setacl` is called if `acl` is specified or if the
        option `set_default_acl` is selected.
        `filesystem.chown` is called if neither `mode` nor `acl` is
        specified.

        The following `options` are supported:

        `set_default_acl` - apply a default ACL appropriate for specified
        dataset. Default ACL is `NFS4_RESTRICTED` or `POSIX_RESTRICTED`
        ACL template builtin with additional entries builtin_users group
        and builtin_administrators group. See documentation for
        `filesystem.acltemplate` for more details.

        `stripacl` - this option must be set in order to apply a POSIX
        mode to a dataset that has a non-trivial ACL. The effect will
        be to remove existing ACL and replace with specified mode.

        `recursive` - apply permissions recursively to dataset (all files
        and directories will be impacted.

        `traverse` - permit recursive job to traverse filesystem boundaries
        (child datasets).

        .. examples(websocket)::

          Change permissions of dataset "tank/myuser" to myuser:wheel and 755.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.dataset.permission",
                "params": ["tank/myuser", {
                    "user": "myuser",
                    "acl": [],
                    "group": "builtin_users",
                    "mode": "755",
                    "options": {"recursive": true, "stripacl": true},
                }]
            }

        """
        dataset_info = await self.middleware.call('pool.dataset.get_instance', id)
        path = dataset_info['mountpoint']
        acltype = dataset_info['acltype']['value']
        user = data.get('user', None)
        group = data.get('group', None)
        uid = gid = -1
        mode = data.get('mode', None)
        options = data.get('options', {})
        set_default_acl = options.pop('set_default_acl')
        acl = data.get('acl', [])

        if mode is None and set_default_acl:
            acl_template = 'POSIX_RESTRICTED' if acltype == 'POSIX' else 'NFS4_RESTRICTED'
            acl = (await self.middleware.call('filesystem.acltemplate.by_path', {
                'query-filters': [('name', '=', acl_template)],
                'format-options': {'canonicalize': True, 'ensure_builtins': True},
            }))[0]['acl']

        pjob = None

        verrors = ValidationErrors()
        if user is not None:
            try:
                uid = (await self.middleware.call('dscache.get_uncached_user', user))['pw_uid']
            except Exception as e:
                verrors.add('pool_dataset_permission.user', str(e))

        if group is not None:
            try:
                gid = (await self.middleware.call('dscache.get_uncached_group', group))['gr_gid']
            except Exception as e:
                verrors.add('pool_dataset_permission.group', str(e))

        if acl and mode:
            verrors.add('pool_dataset_permission.mode',
                        'setting mode and ACL simultaneously is not permitted.')

        if acl and options['stripacl']:
            verrors.add('pool_dataset_permissions.acl',
                        'Simultaneously setting and removing ACL is not permitted.')

        if mode and not options['stripacl']:
            if not await self.middleware.call('filesystem.acl_is_trivial', path):
                verrors.add('pool_dataset_permissions.options',
                            f'{path} has an extended ACL. The option "stripacl" must be selected.')
        verrors.check()

        if not acl and mode is None and not options['stripacl']:
            """
            Neither an ACL, mode, or removing the existing ACL are
            specified in `data`. Perform a simple chown.
            """
            options.pop('stripacl', None)
            pjob = await self.middleware.call('filesystem.chown', {
                'path': path,
                'uid': uid,
                'gid': gid,
                'options': options
            })

        elif acl:
            pjob = await self.middleware.call('filesystem.setacl', {
                'path': path,
                'dacl': acl,
                'uid': uid,
                'gid': gid,
                'options': options
            })

        elif mode or options['stripacl']:
            """
            `setperm` performs one of two possible actions. If
            `mode` is not set, but `stripacl` is specified, then
            the existing ACL on the file is converted in place via
            `acl_strip_np()`. This preserves the existing posix mode
            while removing any extended ACL entries.

            If `mode` is set, then the ACL is removed from the file
            and the new `mode` is applied.
            """
            pjob = await self.middleware.call('filesystem.setperm', {
                'path': path,
                'mode': mode,
                'uid': uid,
                'gid': gid,
                'options': options
            })
        else:
            """
            This should never occur, but fail safely to avoid undefined
            or unintended behavior.
            """
            raise CallError(f"Unexpected parameter combination: {data}",
                            errno.EINVAL)

        await pjob.wait()
        if pjob.error:
            raise CallError(pjob.error)
        return data

    # TODO: Document this please
    @accepts(
        Str('ds', required=True),
        Str('quota_type', enum=['USER', 'GROUP', 'DATASET', 'PROJECT']),
        Ref('query-filters'),
        Ref('query-options'),
    )
    @item_method
    async def get_quota(self, ds, quota_type, filters, options):
        """
        Return a list of the specified `quota_type` of quotas on the ZFS dataset `ds`.
        Support `query-filters` and `query-options`. used_bytes may not instantly
        update as space is used.

        When quota_type is not DATASET, each quota entry has these fields:

        `id` - the uid or gid to which the quota applies.

        `name` - the user or group name to which the quota applies. Value is
        null if the id in the quota cannot be resolved to a user or group. This
        indicates that the user or group does not exist on the server.

        `quota` - the quota size in bytes.  Absent if no quota is set.

        `used_bytes` - the amount of bytes the user has written to the dataset.
        A value of zero means unlimited.

        `obj_quota` - the number of objects that may be owned by `id`.
        A value of zero means unlimited.  Absent if no objquota is set.

        `obj_used` - the number of objects currently owned by `id`.

        Note: SMB client requests to set a quota granting no space will result
        in an on-disk quota of 1 KiB.
        """
        dataset = (await self.middleware.call('pool.dataset.get_instance_quick', ds))['name']
        quota_list = await self.middleware.call(
            'zfs.dataset.get_quota', dataset, quota_type.lower()
        )
        return filter_list(quota_list, filters, options)

    @accepts(
        Str('ds', required=True),
        List('quotas', items=[
            Dict(
                'quota_entry',
                Str('quota_type',
                    enum=['DATASET', 'USER', 'USEROBJ', 'GROUP', 'GROUPOBJ'],
                    required=True),
                Str('id', required=True),
                Int('quota_value', required=True, null=True),
            )
        ], default=[{
            'quota_type': 'USER',
            'id': '0',
            'quota_value': 0
        }])
    )
    @returns()
    @item_method
    async def set_quota(self, ds, data):
        """
        There are three over-arching types of quotas for ZFS datasets.
        1) dataset quotas and refquotas. If a DATASET quota type is specified in
        this API call, then the API acts as a wrapper for `pool.dataset.update`.

        2) User and group quotas. These limit the amount of disk space consumed
        by files that are owned by the specified users or groups. If the respective
        "object quota" type is specfied, then the quota limits the number of objects
        that may be owned by the specified user or group.

        3) Project quotas. These limit the amount of disk space consumed by files
        that are owned by the specified project. Project quotas are not yet implemended.

        This API allows users to set multiple quotas simultaneously by submitting a
        list of quotas. The list may contain all supported quota types.

        `ds` the name of the target ZFS dataset.

        `quotas` specifies a list of `quota_entry` entries to apply to dataset.

        `quota_entry` entries have these required parameters:

        `quota_type`: specifies the type of quota to apply to the dataset. Possible
        values are USER, USEROBJ, GROUP, GROUPOBJ, and DATASET. USEROBJ and GROUPOBJ
        quotas limit the number of objects consumed by the specified user or group.

        `id`: the uid, gid, or name to which the quota applies. If quota_type is
        'DATASET', then `id` must be either `QUOTA` or `REFQUOTA`.

        `quota_value`: the quota size in bytes. Setting a value of `0` removes
        the user or group quota.
        """
        MAX_QUOTAS = 100
        verrors = ValidationErrors()
        if len(data) > MAX_QUOTAS:
            verrors.add(
                'quotas',
                f'The number of user or group quotas that can be set in single API call is limited to {MAX_QUOTAS}.'
            )

        quotas = {}

        ignore = ('PROJECT', 'PROJECTOBJ')  # TODO: not implemented
        for i, q in filter(lambda x: x[1]['id'] not in ignore, enumerate(data)):
            quota_type = q['quota_type'].lower()
            if q['quota_type'] == 'DATASET':
                if q['id'] not in ['QUOTA', 'REFQUOTA']:
                    verrors.add(
                        f'quotas.{i}.id',
                        'id for quota_type DATASET must be either "QUOTA" or "REFQUOTA"'
                    )
                    continue

                xid = q['id'].lower()
                if xid in quotas:
                    verrors.add(
                        f'quotas.{i}.id',
                        f'Setting multiple values for {xid} for quota_type "DATASET" is not permitted'
                    )
                    continue

            else:
                if not q['quota_value']:
                    q['quota_value'] = 'none'

                xid = None

                id_type = 'user' if quota_type.startswith('user') else 'group'
                if not q['id'].isdigit():
                    try:
                        xid_obj = await self.middleware.call(f'{id_type}.get_{id_type}_obj',
                                                             {f'{id_type}name': q['id']})
                        xid = xid_obj['pw_uid'] if id_type == 'user' else xid_obj['gr_gid']
                    except Exception:
                        self.logger.debug("Failed to convert %s [%s] to id.", id_type, q['id'], exc_info=True)
                        verrors.add(
                            f'quotas.{i}.id',
                            f'{quota_type} {q["id"]} is not valid.'
                        )
                else:
                    xid = int(q['id'])

                if xid == 0:
                    verrors.add(
                        f'quotas.{i}.id',
                        f'Setting {quota_type} quota on {id_type[0]}id [{xid}] is not permitted.'
                    )

            quotas[xid] = q

        verrors.check()
        if quotas:
            await self.middleware.call('zfs.dataset.set_quota', ds, quotas)
