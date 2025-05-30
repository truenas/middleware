import libzfs

from middlewared.plugins.zfs_.utils import TNUserProp
from middlewared.service import Service

class ZFSDatasetService(Service):

    class Config:
        namespace = 'zfs.dataset'
        private = True
        process_pool = True

    def query_for_quota_alert(self):
        options = {
            'extra': {
                'properties': [
                    'name',
                    'quota',
                    'available',
                    'refquota',
                    'used',
                    'usedbydataset',
                    'mounted',
                    'mountpoint',
                    TNUserProp.QUOTA_WARN.value,
                    TNUserProp.QUOTA_CRIT.value,
                    TNUserProp.REFQUOTA_WARN.value,
                    TNUserProp.REFQUOTA_CRIT.value,
                ]
            }
        }

        return [
            {k: v for k, v in i['properties'].items() if k in options['extra']['properties']}
            for i in self.middleware.call_sync('zfs.dataset.query', [], options)
        ]

    def set_quota(self, ds, quotas):
        properties = {}
        for quota in quotas:
            for xid, quota_info in quota.items():
                quota_type = quota_info['quota_type'].lower()
                quota_value = {'value': quota_info['quota_value']}
                if quota_type == 'dataset':
                    properties[xid] = quota_value
                else:
                    properties[f'{quota_type}quota@{xid}'] = quota_value

        if properties:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(ds)
                dataset.update_properties(properties)
