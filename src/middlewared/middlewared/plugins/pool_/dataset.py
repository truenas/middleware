import copy

import middlewared.sqlalchemy as sa

from middlewared.schema import Any, Bool, Dict, List, Str
from middlewared.service import CRUDService, filterable, private
from middlewared.utils import filter_list

from .utils import get_props_of_interest_mapping


class PoolDatasetEncryptionModel(sa.Model):
    __tablename__ = 'storage_encrypteddataset'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    encryption_key = sa.Column(sa.EncryptedText(), nullable=True)
    kmip_uid = sa.Column(sa.String(255), nullable=True, default=None)


class PoolDatasetService(CRUDService):

    dataset_store = 'storage.encrypteddataset'
    ENTRY = Dict(
        'pool_dataset_entry',
        Str('id', required=True),
        Str('type', required=True),
        Str('name', required=True),
        Str('pool', required=True),
        Bool('encrypted'),
        Str('encryption_root', null=True),
        Bool('key_loaded', null=True),
        List('children', required=True),
        Dict('user_properties', additional_attrs=True, required=True),
        Bool('locked'),
        *[Dict(
            p[1] or p[0],
            Any('parsed', null=True),
            Str('rawvalue', null=True),
            Str('value', null=True),
            Str('source', null=True),
            Any('source_info', null=True),
        ) for p in get_props_of_interest_mapping() if (p[1] or p[0]) != 'mountpoint'],
        Str('mountpoint', null=True),
    )

    class Config:
        cli_namespace = 'storage.dataset'
        datastore_primary_key_type = 'string'
        event_send = False
        namespace = 'pool.dataset'

    def _internal_user_props(self):
        return [
            'org.freenas:description',
            'org.freenas:quota_warning',
            'org.freenas:quota_critical',
            'org.freenas:refquota_warning',
            'org.freenas:refquota_critical',
            'org.truenas:managedby',
        ]

    def __transform(self, datasets, retrieve_children, children_filters):
        """
        We need to transform the data zfs gives us to make it consistent/user-friendly,
        making it match whatever pool.dataset.{create,update} uses as input.
        """

        def transform(dataset):
            for orig_name, new_name, method in get_props_of_interest_mapping():
                if orig_name not in dataset['properties']:
                    continue
                i = new_name or orig_name
                dataset[i] = dataset['properties'][orig_name]
                if method:
                    dataset[i]['value'] = method(dataset[i]['value'])

            if 'mountpoint' in dataset:
                # This is treated specially to keep backwards compatibility with API
                dataset['mountpoint'] = dataset['mountpoint']['value']
            if dataset['type'] == 'VOLUME':
                dataset['mountpoint'] = None

            dataset['user_properties'] = {
                k: v for k, v in dataset['properties'].items() if ':' in k and k not in self._internal_user_props()
            }
            del dataset['properties']

            if all(k in dataset for k in ('encrypted', 'key_loaded')):
                dataset['locked'] = dataset['encrypted'] and not dataset['key_loaded']

            if retrieve_children:
                rv = []
                for child in filter_list(dataset['children'], children_filters):
                    rv.append(transform(child))
                dataset['children'] = rv

            return dataset

        rv = []
        for dataset in datasets:
            rv.append(transform(dataset))
        return rv

    @private
    async def internal_datasets_filters(self):
        # We get filters here which ensure that we don't match an internal dataset
        return [
            ['pool', '!=', await self.middleware.call('boot.pool_name')],
            ['id', 'rnin', '/.system'],
            ['id', 'rnin', '/.glusterfs'],
            ['id', 'rnin', '/ix-applications/'],
        ]

    @private
    async def is_internal_dataset(self, dataset):
        return not bool(filter_list([{'id': dataset}], await self.internal_datasets_filters()))

    @filterable
    def query(self, filters, options):
        """
        Query Pool Datasets with `query-filters` and `query-options`.

        We provide two ways to retrieve datasets. The first is a flat structure (default), where
        all datasets in the system are returned as separate objects which contain all data
        there is for their children. This retrieval type is slightly slower because of duplicates in each object.
        The second type is hierarchical, where only top level datasets are returned in the list. They contain all the
        children in the `children` key. This retrieval type is slightly faster.
        These options are controlled by the `query-options.extra.flat` attribute (default true).

        In some cases it might be desirable to only retrieve details of a dataset itself and not it's children, in this
        case `query-options.extra.retrieve_children` should be explicitly specified and set to `false` which will
        result in children not being retrieved.

        In case only some properties are desired to be retrieved for datasets, consumer should specify
        `query-options.extra.properties` which when `null` ( which is the default ) will retrieve all properties
        and otherwise a list can be specified like `["type", "used", "available"]` to retrieve selective properties.
        If no properties are desired, in that case an empty list should be sent.

        `query-options.extra.snapshots` can be set to retrieve snapshot(s) of dataset in question.

        `query-options.extra.snapshots_recursive` can be set to retrieve snapshot(s) recursively of dataset in question.
        If `query-options.extra.snapshots_recursive` and `query-options.extra.snapshots` are set, snapshot(s) will be
        retrieved recursively.

        `query-options.extra.snapshots_properties` can be specified to list out properties which should be retrieved
        for snapshot(s) related to each dataset. By default only name of the snapshot would be retrieved, however
        if `null` is specified all properties of the snapshot would be retrieved in this case.
        """
        # Optimization for cases in which they can be filtered at zfs.dataset.query
        zfsfilters = []
        filters = filters or []
        if len(filters) == 1 and len(filters[0]) == 3 and list(filters[0][:2]) == ['id', '=']:
            zfsfilters.append(copy.deepcopy(filters[0]))

        internal_datasets_filters = self.middleware.call_sync('pool.dataset.internal_datasets_filters')
        filters.extend(internal_datasets_filters)
        extra = copy.deepcopy(options.get('extra', {}))
        retrieve_children = extra.get('retrieve_children', True)
        props = extra.get('properties')
        snapshots = extra.get('snapshots')
        snapshots_recursive = extra.get('snapshots_recursive')
        return filter_list(
            self.__transform(self.middleware.call_sync(
                'zfs.dataset.query', zfsfilters, {
                    'extra': {
                        'flat': extra.get('flat', True),
                        'retrieve_children': retrieve_children,
                        'properties': props,
                        'snapshots': snapshots,
                        'snapshots_recursive': snapshots_recursive,
                        'snapshots_properties': extra.get('snapshots_properties', [])
                    }
                }
            ), retrieve_children, internal_datasets_filters,
            ), filters, options
        )
