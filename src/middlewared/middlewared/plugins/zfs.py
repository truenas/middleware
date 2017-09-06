import os
import errno
import socket
import textwrap
import threading
import time

from bsd import geom
import humanfriendly
import libzfs

from middlewared.schema import Dict, List, Str, Bool, Int, accepts
from middlewared.service import (
    CallError, CRUDService, Service, ValidationError, ValidationErrors,
    filterable, job, periodic, private,
)
from middlewared.utils import filter_list


def find_vdev(pool, vname):
    """
    Find a vdev in the given `pool` using `vname` looking for
    guid or path

    Returns:
        libzfs.ZFSVdev object
    """
    children = list(pool.root_vdev.children)
    while children:
        child = children.pop()

        if child.guid == vname:
            return child

        if child.type == 'disk':
            path = child.path.replace('/dev/', '')
            if path == vname:
                return child

        children += list(child.children)


class ZFSPoolService(Service):

    class Config:
        namespace = 'zfs.pool'
        private = True

    @accepts(Str('pool'))
    async def get_disks(self, name):
        zfs = libzfs.ZFS()
        try:
            zpool = zfs.get(name)
        except libzfs.ZFSException as e:
            raise CallError(str(e), errno.ENOENT)

        await self.middleware.threaded(geom.scan)
        labelclass = geom.class_by_name('LABEL')
        for absdev in zpool.disks:
            dev = absdev.replace('/dev/', '').replace('.eli', '')
            find = labelclass.xml.findall(f".//provider[name='{dev}']/../consumer/provider")
            name = None
            if find:
                name = geom.provider_by_id(find[0].get('ref')).geom.name
            else:
                g = geom.geom_by_name('DEV', dev)
                if g:
                    name = g.consumer.provider.geom.name

            if name and geom.geom_by_name('DISK', name):
                yield name
            else:
                self.logger.debug(f'Could not find disk for {dev}')

    @accepts(
        Str('name'),
        List('new'),
        List('existing', items=[
            Dict(
                'attachvdev',
                Str('target'),
                Str('type', enum=['DISK']),
                Str('path'),
            ),
        ]),
    )
    @job()
    def extend(self, job, name, new=None, existing=None):
        """
        Extend a zfs pool `name` with `new` vdevs or attach to `existing` vdevs.
        """

        if new is None and existing is None:
            raise CallError('New or existing vdevs must be provided', errno.EINVAL)

        if new:
            raise CallError('Adding new vdev is not implemented yet')

        try:
            zfs = libzfs.ZFS()
            pool = zfs.get(name)

            # Make sure we can find all target vdev
            for i in (existing or []):
                target = find_vdev(pool, i['target'])
                if target is None:
                    raise CallError(f'Failed to find vdev for {target}', errno.EINVAL)
                i['target'] = target

            for i in (existing or []):
                newvdev = libzfs.ZFSVdev(zfs, i['type'].lower())
                newvdev.path = i['path']
                i['target'].attach(newvdev)

        except libzfs.ZFSException as e:
            raise CallError(str(e), e.code)

    @accepts(Str('pool'), Str('label'))
    def detach(self, name, label):
        """
        Detach device `label` from the pool `pool`.
        """
        try:
            zfs = libzfs.ZFS()
            pool = zfs.get(name)
            target = find_vdev(pool, label)
            if target is None:
                raise CallError(f'Failed to find vdev for {label}', errno.EINVAL)
            target.detach()
        except libzfs.ZFSException as e:
            raise CallError(str(e), e.code)

    @accepts(Str('pool'), Str('label'), Str('dev'))
    def replace(self, name, label, dev):
        """
        Replace device `label` with `dev` in pool `name`.
        """
        try:
            zfs = libzfs.ZFS()
            pool = zfs.get(name)
            target = find_vdev(pool, label)
            if target is None:
                raise CallError(f'Failed to find vdev for {label}', errno.EINVAL)

            newvdev = libzfs.ZFSVdev(zfs, 'disk')
            newvdev.path = f'/dev/{dev}'
            target.replace(newvdev)
        except libzfs.ZFSException as e:
            raise CallError(str(e), e.code)

    @accepts(Str('name'))
    @job(lock=lambda i: i[0])
    def scrub(self, job, name):
        """
        Start a scrub on pool `name`.
        """
        try:
            zfs = libzfs.ZFS()
            pool = zfs.get(name)
            pool.start_scrub()
        except libzfs.ZFSException as e:
            raise CallError(str(e), e.code)

        def watch():
            while True:
                scrub = pool.scrub
                if scrub.function != libzfs.ScanFunction.SCRUB:
                    break

                if scrub.state == libzfs.ScanState.FINISHED:
                    job.set_progress(100, 'Scrub finished')
                    break

                if scrub.state == libzfs.ScanState.CANCELED:
                    break

                if scrub.state == libzfs.ScanState.SCANNING:
                    job.set_progress(scrub.percentage, 'Scrubbing')
                time.sleep(1)

        t = threading.Thread(target=watch, daemon=True)
        t.start()
        t.join()


class ZFSDatasetService(CRUDService):

    class Config:
        namespace = 'zfs.dataset'
        private = True

    @filterable
    def query(self, filters, options):
        zfs = libzfs.ZFS()
        # Handle `id` filter specially to avoiding getting all datasets
        if filters and len(filters) == 1 and list(filters[0][:2]) == ['id', '=']:
            try:
                datasets = [zfs.get_dataset(filters[0][2]).__getstate__()]
            except libzfs.ZFSException:
                datasets = []
        else:
            datasets = [i.__getstate__() for i in zfs.datasets]
        return filter_list(datasets, filters, options)

    @accepts(Dict(
        'dataset_create',
        Str('name', required=True),
        Str('type', enum=['FILESYSTEM', 'VOLUME'], default='FILESYSTEM'),
        Dict(
            'properties',
            Bool('sparse'),
            additional_attrs=True,
        ),
    ))
    def do_create(self, data):
        """
        Creates a ZFS dataset.
        """

        verrors = ValidationErrors()

        if '/' not in data['name']:
            verrors.add('name', 'You need a full name, e.g. pool/newdataset')

        if verrors:
            raise verrors

        properties = data.get('properties') or {}
        sparse = properties.pop('sparse', False)
        params = {}

        for k, v in data['properties'].items():
            params[k] = v

        try:
            zfs = libzfs.ZFS()
            pool = zfs.get(data['name'].split('/')[0])
            pool.create(data['name'], params, fstype=getattr(libzfs.DatasetType, data['type']), sparse_vol=sparse)
        except libzfs.ZFSException as e:
            self.logger.error('Failed to create dataset', exc_info=True)
            raise CallError(f'Failed to create dataset: {e}')

    @accepts(
        Str('id'),
        Dict(
            'dataset_update',
            Dict(
                'properties',
                additional_attrs=True,
            ),
        ),
    )
    def do_update(self, id, data):
        try:
            zfs = libzfs.ZFS()
            dataset = zfs.get_dataset(id)

            if 'properties' in data:
                for k, v in data['properties'].items():

                    # If prop already exists we just update it,
                    # otherwise create a user property
                    prop = dataset.properties.get(k)
                    if prop:
                        if v.get('source') == 'INHERIT':
                            prop.inherit()
                        elif 'value' in v and prop.value != v['value']:
                            prop.value = v['value']
                        elif 'parsed' in v and prop.parsed != v['parsed']:
                            prop.parsed = v['parsed']
                    else:
                        if 'value' not in v:
                            raise ValidationError('properties', f'properties.{k} needs a "value" attribute')
                        if ':' not in v['value']:
                            raise ValidationError('properties', f'User property needs a colon (:) in its name`')
                        prop = libzfs.ZFSUserProperty(v['value'])
                        dataset.properties[k] = prop

        except libzfs.ZFSException as e:
            self.logger.error('Failed to update dataset', exc_info=True)
            raise CallError(f'Failed to update dataset: {e}')

    def do_delete(self, id):
        try:
            zfs = libzfs.ZFS()
            ds = zfs.get_dataset(id)
            ds.delete()
        except libzfs.ZFSException as e:
            self.logger.error('Failed to delete dataset', exc_info=True)
            raise CallError(f'Failed to delete dataset: {e}')


class ZFSSnapshot(CRUDService):

    class Config:
        namespace = 'zfs.snapshot'

    @accepts(Dict(
        'snapshot_create',
        Str('dataset'),
        Str('name'),
        Bool('recursive'),
        Int('vmsnaps_count')
    ))
    async def do_create(self, data):
        """
        Take a snapshot from a given dataset.

        Returns:
            bool: True if succeed otherwise False.
        """
        zfs = libzfs.ZFS()

        dataset = data.get('dataset', '')
        name = data.get('name', '')
        recursive = data.get('recursive', False)
        vmsnaps_count = data.get('vmsnaps_count', 0)

        if not dataset or not name:
            return False

        try:
            ds = zfs.get_dataset(dataset)
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            return False

        try:
            if recursive:
                ds.snapshots('{0}@{1}'.format(dataset, name, recursive=True))
            else:
                ds.snapshot('{0}@{1}'.format(dataset, name))

            if vmsnaps_count > 0:
                ds.properties['freenas:vmsynced'] = libzfs.ZFSUserProperty('Y')

            self.logger.info("Snapshot taken: {0}@{1}".format(dataset, name))
            return True
        except libzfs.ZFSException as err:
                self.logger.error("{0}".format(err))
                return False

    @accepts(Dict(
        'snapshot_remove',
        Str('dataset'),
        Str('name')
    ))
    async def remove(self, data):
        """
        Remove a snapshot from a given dataset.

        Returns:
            bool: True if succeed otherwise False.
        """
        zfs = libzfs.ZFS()

        dataset = data.get('dataset', '')
        snapshot_name = data.get('name', '')

        if not dataset or not snapshot_name:
            return False

        try:
            ds = zfs.get_dataset(dataset)
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            return False

        __snap_name = dataset + '@' + snapshot_name
        try:
            for snap in list(ds.snapshots):
                if snap.name == __snap_name:
                    ds.destroy_snapshot(snapshot_name)
                    self.logger.info("Destroyed snapshot: {0}".format(__snap_name))
                    return True
            self.logger.error("There is no snapshot {0} on dataset {1}".format(snapshot_name, dataset))
            return False
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            return False

    @accepts(Dict(
        'snapshot_clone',
        Str('snapshot'),
        Str('dataset_dst'),
    ))
    async def clone(self, data):
        """
        Clone a given snapshot to a new dataset.

        Returns:
            bool: True if succeed otherwise False.
        """
        zfs = libzfs.ZFS()

        snapshot = data.get('snapshot', '')
        dataset_dst = data.get('dataset_dst', '')

        if not snapshot or not dataset_dst:
            return False

        try:
            snp = zfs.get_snapshot(snapshot)
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            return False

        try:
            snp.clone(dataset_dst)
            self.logger.info("Cloned snapshot {0} to dataset {1}".format(snapshot, dataset_dst))
            return True
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            return False

    @private
    def query(self):
        """
            XXX: Just set it as private and avoid show a query method
                 on the API documentation that was not implemented yet.
        """
        pass


class ZFSQuoteService(Service):

    class Config:
        namespace = 'zfs.quota'
        private = True

    def __init__(self, middleware):
        super().__init__(middleware)

        self.excesses = None

    @periodic(60)
    async def notify_quota_excess(self):
        if self.excesses is None:
            self.excesses = {
                excess["dataset_name"]: excess
                for excess in await self.middleware.call('datastore.query', 'storage.quotaexcess')
            }

        excesses = await self.__get_quota_excess()

        # Remove gone excesses
        self.excesses = dict(
            filter(
                lambda item: any(excess["dataset_name"] == item[0] for excess in excesses),
                self.excesses.items()
            )
        )

        # Insert/update present excesses
        for excess in excesses:
            notify = False
            existing_excess = self.excesses.get(excess["dataset_name"])
            if existing_excess is None:
                notify = True
            else:
                if existing_excess["level"] < excess["level"]:
                    notify = True

            self.excesses[excess["dataset_name"]] = excess

            if notify:
                try:
                    bsduser = await self.middleware.call(
                        'datastore.query',
                        'account.bsdusers',
                        [('bsdusr_uid', '=', excess['uid'])],
                        {'get': True},
                    )
                except IndexError:
                    self.logger.warning('Unable to query bsduser with uid %r', excess['uid'])
                    continue

                hostname = socket.gethostname()

                try:
                    # FIXME: Translation
                    await self.middleware.call('mail.send', {
                        'to': [bsduser['bsdusr_email']],
                        'subject': '{}: Quota exceed on dataset {}'.format(hostname, excess["dataset_name"]),
                        'text': textwrap.dedent('''\
                            Quota exceed on dataset %(dataset_name)s.
                            Used %(percent_used).2f%% (%(used)s of %(available)s)
                        ''') % {
                            "dataset_name": excess["dataset_name"],
                            "percent_used": excess["percent_used"],
                            "used": humanfriendly.format_size(excess["used"]),
                            "available": humanfriendly.format_size(excess["available"]),
                        },
                    })
                except Exception:
                    self.logger.warning('Failed to send email about quota excess', exc_info=True)

    async def __get_quota_excess(self):
        excess = []
        zfs = libzfs.ZFS()
        for properties in await self.middleware.threaded(lambda: [i.properties for i in zfs.datasets]):
            quota = properties.get("quota")
            # zvols do not have a quota property in libzfs
            if quota is None or quota.value == "none":
                continue
            used = int(properties["used"].rawvalue)
            available = used + int(properties["available"].rawvalue)
            try:
                percent_used = 100 * used / available
            except ZeroDivisionError:
                percent_used = 100

            if percent_used >= 95:
                level = 2
            elif percent_used >= 80:
                level = 1
            else:
                continue

            stat_info = await self.middleware.threaded(os.stat, properties["mountpoint"].value)
            uid = stat_info.st_uid

            excess.append({
                "dataset_name": properties["name"].value,
                "level": level,
                "used": used,
                "available": available,
                "percent_used": percent_used,
                "uid": uid,
            })

        return excess

    async def terminate(self):
        await self.middleware.call('datastore.sql', 'DELETE FROM storage_quotaexcess')

        if self.excesses is not None:
            for excess in self.excesses.values():
                await self.middleware.call('datastore.insert', 'storage.quotaexcess', excess)
