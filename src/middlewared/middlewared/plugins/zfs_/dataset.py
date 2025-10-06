import errno
import subprocess

import libzfs
from middlewared.service import CallError, CRUDService, ValidationErrors
from middlewared.utils import filter_list
from .dataset_utils import flatten_datasets
from .utils import get_snapshot_count_cached


class ZFSDatasetService(CRUDService):

    class Config:
        namespace = 'zfs.dataset'
        private = True
        process_pool = True

    def query(self, filters: list | None = None, options: dict | None = None):
        """
        In `query-options` we can provide `extra` arguments which control which data should be retrieved
        for a dataset.

        `query-options.extra.snapshots` is a boolean which when set will retrieve snapshots for the dataset in question
        by adding a snapshots key to the dataset data.

        `query-options.extra.snapshots_count` is a boolean key which when set will retrieve snapshot counts for the
        datasets returned by adding a snapshot_count key to the dataset data.

        `query-options.extra.retrieve_children` is a boolean set to true by default. When set to true, will retrieve
        all children datasets which can cause a performance penalty. When set to false, will not retrieve children
        datasets which does not incur the performance penalty.

        `query-options.extra.properties` is a list of properties which should be retrieved. If null ( by default ),
        it would retrieve all properties, if empty, it will retrieve no property.

        We provide 2 ways how zfs.dataset.query returns dataset's data. First is a flat structure ( default ), which
        means that all the datasets in the system are returned as separate objects which also contain all the data
        their is for their children. This retrieval type is slightly slower because of duplicates which exist in
        each object.
        Second type is hierarchical where only top level datasets are returned in the list and they contain all the
        children there are for them in `children` key. This retrieval type is slightly faster.
        These options are controlled by `query-options.extra.flat` attribute which defaults to true.

        `query-options.extra.user_properties` controls if user defined properties of datasets should be retrieved
        or not.

        While we provide a way to exclude all properties from data retrieval, we introduce a single attribute
        `query-options.extra.retrieve_properties` which if set to false will make sure that no property is retrieved
        whatsoever and overrides any other property retrieval attribute.
        """
        if filters is None:
            filters = list()
        if options is None:
            options = dict()

        options = options or {}
        extra = options.get('extra', {}).copy()
        props = extra.get('properties', None)
        flat = extra.get('flat', True)
        user_properties = extra.get('user_properties', True)
        retrieve_properties = extra.get('retrieve_properties', True)
        retrieve_children = extra.get('retrieve_children', True)
        snapshots = extra.get('snapshots')
        snapshots_count = extra.get('snapshots_count')
        snapshots_recursive = extra.get('snapshots_recursive')
        snapshots_properties = extra.get('snapshots_properties', [])
        if not retrieve_properties:
            # This is a short hand version where consumer can specify that they don't want any property to
            # be retrieved
            user_properties = False
            props = []

        with libzfs.ZFS() as zfs:
            # Handle `id` or `name` filter specially to avoiding getting all datasets
            pop_snapshots_changed = False
            if snapshots_count and props is not None and 'snapshots_changed' not in props:
                props.append('snapshots_changed')
                pop_snapshots_changed = True

            kwargs = dict(
                props=props, user_props=user_properties, snapshots=snapshots, retrieve_children=retrieve_children,
                snapshots_recursive=snapshots_recursive, snapshot_props=snapshots_properties
            )
            if filters and filters[0][0] in ('id', 'name'):
                if filters[0][1] == '=':
                    kwargs['datasets'] = [filters[0][2]]
                if filters[0][1] == 'in':
                    kwargs['datasets'] = filters[0][2]

            datasets = zfs.datasets_serialized(**kwargs)
            if flat:
                datasets = flatten_datasets(datasets)
            else:
                datasets = list(datasets)

            if snapshots_count:
                get_snapshot_count_cached(
                    self.middleware,
                    zfs,
                    datasets,
                    True,
                    pop_snapshots_changed
                )

        return filter_list(datasets, filters, options)

    def delete(self, id_: str, options: dict | None = None):
        """Delete a ZFS dataset or zvol.

        Args:
            id: str (i.e. "tank/dataset")
            options: A dictionary with follow top-level keys
                force: boolean, default False, when True will forcefully
                    delete the dataset/zvol
                recursive: boolean, default False, when True will delete
                    the dataset/zvol recursively
                recursively_remove_dependents: boolean, default False, when
                    True will recursively remove any dependents associated
                    to the dataset/zvol
        """
        if options is None:
            options = dict()

        options.setdefault('force', False)
        options.setdefault('recursive', False)
        options.setdefault('recursively_remove_dependents', False)

        args = []
        if options['force']:
            args += ['-f']
        if options['recursively_remove_dependents']:
            args += ['-R']
        elif options['recursive']:
            args += ['-r']

        # If dataset is mounted and has receive_resume_token, we should destroy it or ZFS will say
        # "cannot destroy 'pool/dataset': dataset already exists"
        recv_run = subprocess.run(['zfs', 'recv', '-A', id_], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Destroying may take a long time, lets not use py-libzfs as it will block
        # other ZFS operations.
        try:
            subprocess.run(
                ['zfs', 'destroy'] + args + [id_], text=True, capture_output=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            if recv_run.returncode == 0 and e.stderr.strip().endswith('dataset does not exist'):
                # This operation might have deleted this dataset if it was created by `zfs recv` operation
                return
            error = e.stderr.strip()
            errno_ = errno.EFAULT
            if 'Device busy' in error or 'dataset is busy' in error:
                errno_ = errno.EBUSY
            raise CallError(f'Failed to delete dataset: {error}', errno_)
        return True

    def destroy_snapshots(self, name, snapshot_spec):
        try:
            with libzfs.ZFS() as zfs:
                dataset = zfs.get_dataset(name)
                return dataset.delete_snapshots(snapshot_spec)
        except libzfs.ZFSException as e:
            raise CallError(str(e))

    def update_zfs_object_props(self, properties, zfs_object):
        verrors = ValidationErrors()
        for k, v in properties.items():
            # If prop already exists we just update it,
            # otherwise create a user property
            prop = zfs_object.properties.get(k)
            if v.get('source') == 'INHERIT':
                if not prop:
                    verrors.add(f'properties.{k}', 'Property does not exist and cannot be inherited')
            else:
                if not any(i in v for i in ('parsed', 'value')):
                    verrors.add(f'properties.{k}', '"value" or "parsed" must be specified when setting a property')
                if not prop and ':' not in k:
                    verrors.add(f'properties.{k}', 'User property needs a colon (:) in its name')

        verrors.check()

        try:
            zfs_object.update_properties(properties)
        except libzfs.ZFSException as e:
            raise CallError(f'Failed to update properties: {e!r}')
