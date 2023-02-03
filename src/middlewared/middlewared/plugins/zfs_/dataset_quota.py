import libzfs

from middlewared.service import CallError, Service


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
                    'org.freenas:quota_warning',
                    'org.freenas:quota_critical',
                    'org.freenas:refquota_warning',
                    'org.freenas:refquota_critial',
                ]
            }
        }
        return [
            {k: v for k, v in i['properties'].items() if k in options['extra']['properties']}
            for i in self.middleware.call_sync('zfs.dataset.query', [], options)
        ]

    # quota_type in ('USER', 'GROUP', 'DATASET', 'PROJECT')
    def get_quota(self, ds, quota_type):
        quota_type = quota_type.upper()
        if quota_type == 'DATASET':
            dataset = self.middleware.call_sync('zfs.dataset.query', [('id', '=', ds)], {'get': True})
            return [{
                'quota_type': quota_type,
                'id': ds,
                'name': ds,
                'quota': int(dataset['properties']['quota']['rawvalue']),
                'refquota': int(dataset['properties']['refquota']['rawvalue']),
                'used_bytes': int(dataset['properties']['used']['rawvalue']),
            }]
        elif quota_type == 'USER':
            quota_props = [
                libzfs.UserquotaProp.USERUSED,
                libzfs.UserquotaProp.USERQUOTA,
                libzfs.UserquotaProp.USEROBJUSED,
                libzfs.UserquotaProp.USEROBJQUOTA
            ]
        elif quota_type == 'GROUP':
            quota_props = [
                libzfs.UserquotaProp.GROUPUSED,
                libzfs.UserquotaProp.GROUPQUOTA,
                libzfs.UserquotaProp.GROUPOBJUSED,
                libzfs.UserquotaProp.GROUPOBJQUOTA
            ]
        elif quota_type == 'PROJECT':
            quota_props = [
                libzfs.UserquotaProp.PROJECTUSED,
                libzfs.UserquotaProp.PROJECTQUOTA,
                libzfs.UserquotaProp.PROJECTOBJUSED,
                libzfs.UserquotaProp.PROJECTOBJQUOTA
            ]
        else:
            raise CallError(f'Unknown quota type {quota_type}')

        try:
            with libzfs.ZFS() as zfs:
                resource = zfs.get_object(ds)
                quotas = resource.userspace(quota_props)
        except libzfs.ZFSException:
            raise CallError(f'Failed retreiving {quota_type} quotas for {ds}')

        # We get the quotas in separate lists for each prop.  Collect these into
        # a single list of objects containing all the requested props.  Each
        # object is unique by (domain, rid), and we only work with POSIX ids,
        # so we use rid as a dict key and update the values as we iterate
        # through all the quotas.
        keymap = {
            libzfs.UserquotaProp.USERUSED: 'used_bytes',
            libzfs.UserquotaProp.GROUPUSED: 'used_bytes',
            libzfs.UserquotaProp.PROJECTUSED: 'used_bytes',
            libzfs.UserquotaProp.USERQUOTA: 'quota',
            libzfs.UserquotaProp.GROUPQUOTA: 'quota',
            libzfs.UserquotaProp.PROJECTQUOTA: 'quota',
            libzfs.UserquotaProp.USEROBJUSED: 'obj_used',
            libzfs.UserquotaProp.GROUPOBJUSED: 'obj_used',
            libzfs.UserquotaProp.PROJECTOBJUSED: 'obj_used',
            libzfs.UserquotaProp.USEROBJQUOTA: 'obj_quota',
            libzfs.UserquotaProp.GROUPOBJQUOTA: 'obj_quota',
            libzfs.UserquotaProp.PROJECTOBJQUOTA: 'obj_quota',
        }
        collected = {}
        for quota_prop, quota_list in quotas.items():
            for quota in quota_list:
                # We only use POSIX ids, skip anything with a domain.
                if quota['domain'] != '':
                    continue
                rid = quota['rid']
                entry = collected.get(rid, {
                    'quota_type': quota_type,
                    'id': rid
                })
                key = keymap[quota_prop]
                entry[key] = quota['space']
                collected[rid] = entry

        # Do name lookups last so we aren't repeating for all the quota props
        # for each entry.
        def add_name(entry):
            try:
                if quota_type == 'USER':
                    entry['name'] = self.middleware.call_sync('user.get_user_obj', {'uid': entry['id']})['pw_name']
                elif quota_type == 'GROUP':
                    entry['name'] = self.middleware.call_sync('group.get_group_obj', {'gid': entry['id']})['gr_name']
            except Exception:
                self.logger.debug('Unable to resolve %s id %d to name', quota_type.lower(), entry['id'])
            return entry

        return [add_name(entry) for entry in collected.values()]

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
