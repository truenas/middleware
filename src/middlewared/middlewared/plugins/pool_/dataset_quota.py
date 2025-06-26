from collections import defaultdict

from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetGetQuotaArgs,
    PoolDatasetGetQuotaResult,
    PoolDatasetSetQuotaArgs,
    PoolDatasetSetQuotaResult
)
from middlewared.plugins.zfs_.utils import TNUserProp
from middlewared.service import private, Service
from middlewared.service.decorators import pass_thread_local_storage
from middlewared.service_exception import ValidationError
from middlewared.utils import filter_list
from middlewared.utils.nss import pwd, grp
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
        truenas_pylibzfs.ZFSUserQuota.USER_QUOTA,
        truenas_pylibzfs.ZFSUserQuota.GROUP_QUOTA,
    ):
        value_key = 'quota'
    elif quota.quota_type in (
        truenas_pylibzfs.ZFSUserQuota.USEROBJ_USED,
        truenas_pylibzfs.ZFSUserQuota.GROUPOBJ_USED,
    ):
        value_key = 'obj_used'
    elif quota.quota_type in (
        truenas_pylibzfs.ZFSUserQuota.USEROBJ_QUOTA,
        truenas_pylibzfs.ZFSUserQuota.GROUPOBJ_QUOTA,
    ):
        value_key = 'obj_quota'
    else:
        # shouldn't be reachable but return early
        # to be safe
        return True

    entry = {'quota_type': state['qt'], 'id': quota.xid, value_key: quota.value}
    if quota.xid not in state['quotas']:
        # only resolve the xid once
        try:
            if state['qt'] == 'USER':
                entry['name'] = pwd.getpwuid(quota.xid, as_dict=True)['pw_name']
            else:
                entry['name'] = grp.getgrgid(quota.xid, as_dict=True)['gr_name']
        except Exception:
            pass
    else:
        entry.update({'name': state['quotas'][quota.xid]['name']})

    state['quotas'][quota.xid].update(entry)
    return True


def quota_alert_cb(hdl, state):
    if hdl.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_VOLUME:
        return True

    info = hdl.asdict(
        properties={
            truenas_pylibzfs.ZFSProperty.USED,
            truenas_pylibzfs.ZFSProperty.USEDBYDATASET,
            truenas_pylibzfs.ZFSProperty.QUOTA,
            truenas_pylibzfs.ZFSProperty.REFQUOTA,
            truenas_pylibzfs.ZFSProperty.AVAILABLE,
            truenas_pylibzfs.ZFSProperty.MOUNTED,
            truenas_pylibzfs.ZFSProperty.MOUNTPOINT,
        },
        get_user_properties=True,
    )
    for propstring, default in TNUserProp.quotas():
        info['user_properties'].setdefault(propstring, default)
        try:
            info['user_propertites'] = int(info['user_properties'][propstring])
        except Exception:
            # if we can't parse this (i.e. someone changed something by hand)
            # we'll play it safe and just default to 0
            info['user_propertites'] = 0

    if hdl.name == hdl.pool_name:
        state['pools'][hdl.name] = info['properties']['used']['value'] + info['properties']['available']['value']

    state['datasets'][hdl.name] = info
    hdl.iter_filesystems(callback=quota_alert_cb, state=state, fast=True)
    return True


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @private
    @pass_thread_local_storage
    def query_for_quota_alert(self, tls):
        """Called, at time of writing, exclusively
        by our alert system to inform users of quota
        thresholds."""
        state = {"pools": dict(), "datasets": dict()}
        tls.lzh.iter_root_filesystems(callback=quota_alert_cb, state=state)
        return state

    @private
    @pass_thread_local_storage
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
                state = {'qt': quota_type, 'quotas': defaultdict(dict)}
                for qt in (
                    getattr(truenas_pylibzfs.ZFSUserQuota, f'{quota_type}_USED'),
                    getattr(truenas_pylibzfs.ZFSUserQuota, f'{quota_type}_QUOTA'),
                    getattr(truenas_pylibzfs.ZFSUserQuota, f'{quota_type}OBJ_USED'),
                    getattr(truenas_pylibzfs.ZFSUserQuota, f'{quota_type}OBJ_QUOTA'),
                ):
                    rsrc.iter_userspace(callback=quota_cb, quota_type=qt, state=state)
                return list(state['quotas'].values())
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

    @private
    @pass_thread_local_storage
    def set_quota_impl(self, tls, ds, inquotas):
        ds_quotas, quotas = dict(), list()
        for i in inquotas:
            if i['quota_type'] == 'DATASET':
                ds_quotas[truenas_pylibzfs.ZFSProperty[i['id']]] = i['quota_value']
            else:
                qt = truenas_pylibzfs.ZFSUserQuota[f'{i["quota_type"]}_QUOTA']
                quotas.append(
                    {
                        'xid': i['id'],
                        'quota_type': qt,
                        'value': i['quota_value']
                    }
                )

        rsrc = tls.lzh.open_resource(name=ds)
        if ds_quotas:
            rsrc.set_properties(properties=ds_quotas)
        if quotas:
            rsrc.set_userquotas(quotas=quotas)

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
