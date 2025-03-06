from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetGetQuotaArgs, PoolDatasetGetQuotaResult, PoolDatasetSetQuotaArgs, PoolDatasetSetQuotaResult
)
from middlewared.service import item_method, Service, ValidationErrors
from middlewared.utils import filter_list


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    # TODO: Document this please
    @api_method(PoolDatasetGetQuotaArgs, PoolDatasetGetQuotaResult, roles=['DATASET_READ'])
    @item_method
    async def get_quota(self, ds, quota_type, filters, options):
        """
        Return a list of the specified `quota_type` of quotas on the ZFS dataset `ds`.
        Support `query-filters` and `query-options`.

        Note: SMB client requests to set a quota granting no space will result
        in an on-disk quota of 1 KiB.
        """
        dataset = (await self.middleware.call('pool.dataset.get_instance_quick', ds))['name']
        quota_list = await self.middleware.call(
            'zfs.dataset.get_quota', dataset, quota_type.lower()
        )
        return filter_list(quota_list, filters, options)

    @api_method(PoolDatasetSetQuotaArgs, PoolDatasetSetQuotaResult, roles=['DATASET_WRITE'])
    @item_method
    async def set_quota(self, ds, data):
        """
        Allow users to set multiple quotas simultaneously by submitting a list of quotas.
        """
        verrors = ValidationErrors()
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
