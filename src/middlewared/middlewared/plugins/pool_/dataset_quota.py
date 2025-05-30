from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetGetQuotaArgs,
    PoolDatasetGetQuotaResult,
    PoolDatasetSetQuotaArgs,
    PoolDatasetSetQuotaResult
)
from middlewared.service import private, Service
from middlewared.service.decorators import pass_thread_local_storage
from middlewared.service_exception import ValidationError
from middlewared.utils import filter_list

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None

def quota_cb(quota, state):
    if quota.quota_type in (
        truenas_pylibzfs.ZFSUserQuota.USER_USED,
        truenas_pylibzfs.ZFSUserQuota.GROUP_USED,
    ):
        value_key = 'used_bytes'
    elif quota.quota_type in (
        truenas_pylibzfs.ZFSUserQuota.USEROBJ_USED,
        truenas_pylibzfs.ZFSUserQuota.GROUPOBJ_USED,
    ):
        value_key = 'obj_used'
    elif quota.quota_type in (
        truenas_pylibzfs.ZFSUserQuota.USER_QUOTA,
        truenas_pylibzfs.ZFSUserQuota.GROUP_QUOTA,
    ):
        value_key = 'quota'
    elif quota.quota_type in (
        truenas_pylibzfs.ZFSUserQuota.USEROBJ_QUOTA,
        truenas_pylibzfs.ZFSUserQuota.GROUPOBJ_QUOTA,
    ):
        value_key = 'obj_quota'

    state['quotas'].append({
        'quota_type': state['qt'],
        'id': quota.xid,
        value_key: quota.value,
    })


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @pass_thread_local_storage
    @private
    def get_quota_impl(self, tls, ds, quota_type):
        rsrc = tls.lzh.open_resource(name=ds)
        quota_type = quota_type.upper()
        match quota_type:
            case 'DATASET':
                info = rsrc.asdict(
                    properties={
                        truenas_pylibzfs.ZFSProperty.QUOTA,
                        truenas_pylibzfs.ZFSProperty.REFQUOTA,
                        truenas_pylibzfs.ZFSProperty.USED,
                    }
                )
                return [{
                    'quota_type': quota_type,
                    'id': rsrc.name,
                    'name': rsrc.name,
                    'quota': info['properties']['quota']['value'],
                    'refquota': info['properties']['refquota']['value'],
                    'used_bytes': info['properties']['used']['value'],
                }]
            case 'USER' | 'GROUP':
                state = {'qt': quota_type, 'quotas': list()}
                for qt in (
                    getattr(truenas_pylibzfs.ZFSUserQuota, f'{quota_type}_USED'),
                    getattr(truenas_pylibzfs.ZFSUserQuota, f'{quota_type}OBJ_USED'),
                    getattr(truenas_pylibzfs.ZFSUserQuota, f'{quota_type}_QUOTA'),
                    getattr(truenas_pylibzfs.ZFSUserQuota, f'{quota_type}OBJ_QUOTA'),
                ):
                    rsrc.iter_userspace(callback=quota_cb, quota_type=qt, state=state)

                qtl = quota_type.lower()
                for i in state['quotas']:
                    # resolve uid/gid to name
                    i['name'] = self.middleware.call_sync(
                        f'{qtl}.get_{qtl}_obj', {f'{qtl[0]}id': i['id']}
                    )['pw_name' if qtl == 'user' else 'gr_name']
            case _:
                raise ValidationError(
                    'pool.dataset.get_quota', f'Invalid quota type: {quota_type!r}'
                )

    @api_method(
        PoolDatasetGetQuotaArgs,
        PoolDatasetGetQuotaResult,
        roles=['DATASET_READ']
    )
    async def get_quota(self, ds, quota_type, filters, options):
        """
        Return a list of the specified `quota_type` of quotas on the ZFS dataset `ds`.
        Support `query-filters` and `query-options`.

        Note: SMB client requests to set a quota granting no space will result
        in an on-disk quota of 1 KiB.
        """
        quota_list = await self.middleware.call(
            'pool.dataset.get_quota_impl', ds, quota_type
        )
        return filter_list(quota_list, filters, options)

    @pass_thread_local_storage
    @private
    def set_quota_impl(self, tls, ds, inquotas):
        ds_quotas, quotas = dict(), list()
        for i in inquotas:
            if i['quota_type'] == 'DATASET':
                ds_quotas[truenas_pylibzfs.ZFSProperty[i['id']]] = i['quota_value']
            else:
                quotas.append(
                    {
                        'xid': i['id'],
                        'quota_type': truenas_pylibzfs.ZFSUserQuota[i['quota_type']],
                        'value': i['quota_value']
                    }
                )

        rsrc = tls.lzh.open_resource(name=ds)
        if ds_quotas:
            rsrc.set_properties(properties=ds_quotas)
        if quotas:
            rsrc.set_quotas(quotas=quotas)

    @api_method(
        PoolDatasetSetQuotaArgs,
        PoolDatasetSetQuotaResult,
        roles=['DATASET_WRITE']
    )
    async def set_quota(self, ds, data):
        """
        Allow users to set multiple quotas simultaneously by submitting a list of quotas.
        """
        quotas = []
        for i, q in enumerate(data):
            quota_type = q['quota_type'].lower()
            if q['quota_type'] == 'DATASET':
                if q['id'] not in ('QUOTA', 'REFQUOTA'):
                    raise ValidationError(
                        f'quotas.{i}.id',
                        'id for quota_type DATASET must be either "QUOTA" or "REFQUOTA"'
                    )
                else:
                    xid = q['id'].lower()
                    if any((i.get(xid, False) for i in quotas)):
                        raise ValidationError(
                            f'quotas.{i}.id',
                            f'Setting multiple values for {xid} for quota_type DATASET is not permitted'
                        )
            else:
                if q['quota_value'] == 0:
                    # value of 0 means remove
                    q['quota_value'] = None

                xid = None
                id_type = 'user' if quota_type.startswith('user') else 'group'
                if not q['id'].isdigit():
                    try:
                        xid = (await self.middleware.call(
                            f'{id_type}.get_{id_type}_obj',
                            {f'{id_type}name': q['id']}
                        ))['pw_uid' if id_type == 'user' else 'gr_gid']
                    except Exception:
                        self.logger.debug('Failed to convert %s [%s] to id.', id_type, q['id'], exc_info=True)
                        raise ValidationError(f'quotas.{i}.id', f'{quota_type} {q["id"]} is not valid.')
                else:
                    xid = int(q['id'])

                if xid == 0:
                    raise ValidationError(
                        f'quotas.{i}.id',
                        f'Setting {quota_type} quota on {id_type[0]}id [{xid}] is not permitted'
                    )
                q['id'] = xid

            quotas.append(q)

        if quotas:
            await self.middleware.call('pool.dataset.set_quota_impl', ds, quotas)
