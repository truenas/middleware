from middlewared.schema import accepts, Dict, Int, List, Ref, returns, Str
from middlewared.service import item_method, Service, ValidationErrors
from middlewared.utils import filter_list


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    # TODO: Document this please
    @accepts(
        Str('ds', required=True),
        Str('quota_type', enum=['USER', 'GROUP', 'DATASET', 'PROJECT']),
        Ref('query-filters'),
        Ref('query-options'),
        roles=['DATASET_READ']
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
        }]),
        roles=['DATASET_WRITE']
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
            # no reason to continue
            raise ValidationErrors(
                'quotas',
                f'The number of user or group quotas that can be set in single API call is limited to {MAX_QUOTAS}.'
            )

        quotas = []
        ignore = ('PROJECT', 'PROJECTOBJ')  # TODO: not implemented
        for i, q in filter(lambda x: x[1]['quota_type'] not in ignore, enumerate(data)):
            quota_type = q['quota_type'].lower()
            if q['quota_type'] == 'DATASET':
                if q['id'] not in ('QUOTA', 'REFQUOTA'):
                    verrors.add(f'quotas.{i}.id', 'id for quota_type DATASET must be either "QUOTA" or "REFQUOTA"')
                else:
                    xid = q['id'].lower()
                    if any((i.get(xid, False) for i in quotas)):
                        verrors.add(
                            f'quotas.{i}.id',
                            f'Setting multiple values for {xid} for quota_type DATASET is not permitted'
                        )
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
                        self.logger.debug('Failed to convert %s [%s] to id.', id_type, q['id'], exc_info=True)
                        verrors.add(f'quotas.{i}.id', f'{quota_type} {q["id"]} is not valid.')
                else:
                    xid = int(q['id'])

                if xid == 0:
                    verrors.add(
                        f'quotas.{i}.id', f'Setting {quota_type} quota on {id_type[0]}id [{xid}] is not permitted'
                    )

            quotas.append({xid: q})

        verrors.check()
        if quotas:
            await self.middleware.call('zfs.dataset.set_quota', ds, quotas)
