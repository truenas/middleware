#-
# Copyright (c) 2014 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

from libc.stdint cimport uintptr_t
import enum
import datetime
import nvpair
cimport nvpair
cimport libzfs
cimport zfs


class Error(enum.IntEnum):
    SUCCESS = libzfs.EZFS_SUCCESS
    NOMEM = libzfs.EZFS_NOMEM
    BADPROP = libzfs.EZFS_BADPROP
    PROPREADONLY = libzfs.EZFS_PROPREADONLY
    PROPTYPE = libzfs.EZFS_PROPTYPE
    PROPNONINHERIT = libzfs.EZFS_PROPNONINHERIT
    PROPSPACE = libzfs.EZFS_PROPSPACE
    BADTYPE = libzfs.EZFS_BADTYPE
    BUSY = libzfs.EZFS_BUSY
    EXISTS = libzfs.EZFS_EXISTS
    NOENT = libzfs.EZFS_NOENT
    BADSTREAM = libzfs.EZFS_BADSTREAM
    DSREADONLY = libzfs.EZFS_DSREADONLY
    VOLTOOBIG = libzfs.EZFS_VOLTOOBIG
    INVALIDNAME = libzfs.EZFS_INVALIDNAME
    BADRESTORE = libzfs.EZFS_BADRESTORE
    BADBACKUP = libzfs.EZFS_BADBACKUP
    BADTARGET = libzfs.EZFS_BADTARGET
    NODEVICE = libzfs.EZFS_NODEVICE
    BADDEV = libzfs.EZFS_BADDEV
    NOREPLICAS = libzfs.EZFS_NOREPLICAS
    RESILVERING = libzfs.EZFS_RESILVERING
    BADVERSION = libzfs.EZFS_BADVERSION
    POOLUNAVAIL = libzfs.EZFS_POOLUNAVAIL
    DEVOVERFLOW = libzfs.EZFS_DEVOVERFLOW
    BADPATH = libzfs.EZFS_BADPATH
    CROSSTARGET = libzfs.EZFS_CROSSTARGET
    ZONED = libzfs.EZFS_ZONED
    MOUNTFAILED = libzfs.EZFS_MOUNTFAILED
    UMOUNTFAILED = libzfs.EZFS_UMOUNTFAILED
    UNSHARENFSFAILED = libzfs.EZFS_UNSHARENFSFAILED
    SHARENFSFAILED = libzfs.EZFS_SHARENFSFAILED
    PERM = libzfs.EZFS_PERM
    NOSPC = libzfs.EZFS_NOSPC
    FAULT = libzfs.EZFS_FAULT
    IO = libzfs.EZFS_IO
    INTR = libzfs.EZFS_INTR
    ISSPARE = libzfs.EZFS_ISSPARE
    INVALCONFIG = libzfs.EZFS_INVALCONFIG
    RECURSIVE = libzfs.EZFS_RECURSIVE
    NOHISTORY = libzfs.EZFS_NOHISTORY
    POOLPROPS = libzfs.EZFS_POOLPROPS
    POOL_NOTSUP = libzfs.EZFS_POOL_NOTSUP
    INVALARG = libzfs.EZFS_POOL_INVALARG
    NAMETOOLONG = libzfs.EZFS_NAMETOOLONG
    OPENFAILED = libzfs.EZFS_OPENFAILED
    NOCAP = libzfs.EZFS_NOCAP
    LABELFAILED = libzfs.EZFS_LABELFAILED
    BADWHO = libzfs.EZFS_BADWHO
    BADPERM = libzfs.EZFS_BADPERM
    BADPERMSET = libzfs.EZFS_BADPERMSET
    NODELEGATION = libzfs.EZFS_NODELEGATION
    UNSHARESMBFAILED = libzfs.EZFS_UNSHARESMBFAILED
    SHARESMBFAILED = libzfs.EZFS_SHARESMBFAILED
    BADCACHE = libzfs.EZFS_BADCACHE
    ISL2CACHE = libzfs.EZFS_ISL2CACHE
    VDEVNOTSUP = libzfs.EZFS_VDEVNOTSUP
    NOTSUP = libzfs.EZFS_NOTSUP
    SPARE = libzfs.EZFS_ACTIVE_SPARE
    LOGS = libzfs.EZFS_UNPLAYED_LOGS
    RELE = libzfs.EZFS_REFTAG_RELE
    HOLD = libzfs.EZFS_REFTAG_HOLD
    TAGTOOLONG = libzfs.EZFS_TAGTOOLONG
    PIPEFAILED = libzfs.EZFS_PIPEFAILED
    THREADCREATEFAILED = libzfs.EZFS_THREADCREATEFAILED
    ONLINE = libzfs.EZFS_POSTSPLIT_ONLINE
    SCRUBBING = libzfs.EZFS_SCRUBBING
    SCRUB = libzfs.EZFS_NO_SCRUB
    DIFF = libzfs.EZFS_DIFF
    DIFFDATA = libzfs.EZFS_DIFFDATA
    POOLREADONLY = libzfs.EZFS_POOLREADONLY
    UNKNOWN = libzfs.EZFS_UNKNOWN


class PropertySource(enum.IntEnum):
    NONE = zfs.ZPROP_SRC_NONE
    DEFAULT = zfs.ZPROP_SRC_DEFAULT
    TEMPORARY = zfs.ZPROP_SRC_TEMPORARY
    LOCAL = zfs.ZPROP_SRC_LOCAL
    INHERITED = zfs.ZPROP_SRC_INHERITED
    RECEIVED = zfs.ZPROP_SRC_RECEIVED


class VDevState(enum.IntEnum):
    UNKNOWN = zfs.VDEV_STATE_UNKNOWN
    CLOSED = zfs.VDEV_STATE_CLOSED
    OFFLINE = zfs.VDEV_STATE_OFFLINE
    REMOVED = zfs.VDEV_STATE_REMOVED
    CANT_OPEN = zfs.VDEV_STATE_CANT_OPEN
    FAULTED = zfs.VDEV_STATE_FAULTED
    DEGRADED = zfs.VDEV_STATE_DEGRADED
    HEALTHY = zfs.VDEV_STATE_HEALTHY


class PoolState(enum.IntEnum):
    ACTIVE = zfs.POOL_STATE_ACTIVE
    EXPORTED = zfs.POOL_STATE_EXPORTED
    DESTROYED = zfs.POOL_STATE_DESTROYED
    SPARE = zfs.POOL_STATE_SPARE
    L2CACHE = zfs.POOL_STATE_L2CACHE
    UNINITIALIZED = zfs.POOL_STATE_UNINITIALIZED
    UNAVAIL = zfs.POOL_STATE_UNAVAIL
    POTENTIALLY_ACTIVE = zfs.POOL_STATE_POTENTIALLY_ACTIVE


class PoolStatus(enum.IntEnum):
    CORRUPT_CACHE = libzfs.ZPOOL_STATUS_CORRUPT_CACHE
    MISSING_DEV_R = libzfs.ZPOOL_STATUS_MISSING_DEV_R
    MISSING_DEV_NR = libzfs.ZPOOL_STATUS_MISSING_DEV_NR
    CORRUPT_LABEL_R = libzfs.ZPOOL_STATUS_CORRUPT_LABEL_R
    CORRUPT_LABEL_NR = libzfs.ZPOOL_STATUS_CORRUPT_LABEL_NR
    BAD_GUID_SUM = libzfs.ZPOOL_STATUS_BAD_GUID_SUM
    CORRUPT_POOL = libzfs.ZPOOL_STATUS_CORRUPT_POOL
    CORRUPT_DATA = libzfs.ZPOOL_STATUS_CORRUPT_DATA
    FAILING_DEV = libzfs.ZPOOL_STATUS_FAILING_DEV
    VERSION_NEWER = libzfs.ZPOOL_STATUS_VERSION_NEWER
    HOSTID_MISMATCH = libzfs.ZPOOL_STATUS_HOSTID_MISMATCH
    IO_FAILURE_WAIT = libzfs.ZPOOL_STATUS_IO_FAILURE_WAIT
    IO_FAILURE_CONTINUE = libzfs.ZPOOL_STATUS_IO_FAILURE_CONTINUE
    BAD_LOG = libzfs.ZPOOL_STATUS_BAD_LOG
    UNSUP_FEAT_READ = libzfs.ZPOOL_STATUS_UNSUP_FEAT_READ
    UNSUP_FEAT_WRITE = libzfs.ZPOOL_STATUS_UNSUP_FEAT_WRITE
    FAULTED_DEV_R = libzfs.ZPOOL_STATUS_FAULTED_DEV_R
    FAULTED_DEV_NR = libzfs.ZPOOL_STATUS_FAULTED_DEV_NR
    VERSION_OLDER = libzfs.ZPOOL_STATUS_VERSION_OLDER
    FEAT_DISABLED = libzfs.ZPOOL_STATUS_FEAT_DISABLED
    RESILVERING = libzfs.ZPOOL_STATUS_RESILVERING
    OFFLINE_DEV = libzfs.ZPOOL_STATUS_OFFLINE_DEV
    REMOVED_DEV = libzfs.ZPOOL_STATUS_REMOVED_DEV
    NON_NATIVE_ASHIFT = libzfs.ZPOOL_STATUS_NON_NATIVE_ASHIFT
    OK = libzfs.ZPOOL_STATUS_OK


class ScanState(enum.IntEnum):
    NONE = zfs.DSS_NONE
    SCANNING = zfs.DSS_SCANNING
    FINISHED = zfs.DSS_FINISHED
    CANCELED = zfs.DSS_CANCELED


class ZFSException(RuntimeError):
    def __init__(self, code, message):
        super(ZFSException, self).__init__(message)
        self.code = code


cdef class ZFS(object):
    cdef libzfs.libzfs_handle_t *_root

    def __cinit__(self):
        self._root = libzfs.libzfs_init()

    def __dealloc__(self):
        libzfs.libzfs_fini(self._root)

    cdef uintptr_t handle(self):
        return <uintptr_t>self._root

    def __getstate__(self):
        return [p.__getstate__() for p in self.pools]

    @staticmethod
    cdef int __iterate_pools(libzfs.zpool_handle_t *handle, void *arg):
        pools = <object>arg
        pools.append(<uintptr_t>handle)

    def __make_vdev_tree(self, topology):
        root = ZFSVdev(self)
        root.type = 'root'
        root.children = topology['data']

        if 'cache' in topology:
            root.nvlist['l2cache'] = topology['cache']

        if 'log' in topology:
            for i in topology['log']:
                i.nvlist['is_log'] = 1
                root.add_child_vdev(i)

        return root

    property errno:
        def __get__(self):
            return Error(libzfs.libzfs_errno(self._root))

    property errstr:
        def __get__(self):
            return libzfs.libzfs_error_description(self._root)

    property pools:
        def __get__(self):
            pools = []
            libzfs.zpool_iter(self._root, self.__iterate_pools, <void *>pools)
            return [ZFSPool(self, h) for h in pools]

    def get(self, name):
        cdef libzfs.zpool_handle_t *handle = libzfs.zpool_open(self._root, name)
        if handle == NULL:
            raise ZFSException(Error.NOENT, 'Pool {0} not found'.format(name))

        return ZFSPool(self, <uintptr_t>handle)

    def get_dataset(self, name):
        cdef libzfs.zfs_handle_t *handle = libzfs.zfs_open(self._root, name, zfs.ZFS_TYPE_FILESYSTEM)
        cdef libzfs.zpool_handle_t *pool = libzfs.zfs_get_pool_handle(handle)
        if handle == NULL:
            raise ZFSException(Error.NOENT, 'Dataset {0} not found'.format(name))

        return ZFSDataset(self, ZFSPool(self, <uintptr_t>pool), <uintptr_t>handle)

    def create(self, name, topology, opts, fsopts):
        root = self.__make_vdev_tree(topology)
        cdef uintptr_t croot = root.nvlist.handle()
        cdef uintptr_t copts = opts.handle()
        cdef uintptr_t cfsopts = fsopts.handle()

        if libzfs.zpool_create(
            self._root,
            name,
            <nvpair.nvlist_t*>croot,
            <nvpair.nvlist_t*>copts,
            <nvpair.nvlist_t*>cfsopts) != 0:
            raise ZFSException(self.errno, self.errstr)

        return self.get(name)

    def destroy(self, name):
        cdef libzfs.zpool_handle_t *handle = libzfs.zpool_open(self._root, name)
        if handle == NULL:
            raise ZFSException(Error.NOENT, 'Pool {0} not found'.format(name))

        if libzfs.zpool_destroy(handle, "destroy") != 0:
            raise ZFSException(self.errno, self.errstr)


cdef class ZPoolProperty(object):
    cdef libzfs.libzfs_handle_t* _root
    cdef libzfs.zpool_handle_t* _zpool
    cdef zfs.zpool_prop_t _propid
    cdef readonly object name

    def __init__(self, ZFS root, ZFSPool pool, zfs.zpool_prop_t propid):
        self._root = <libzfs.libzfs_handle_t*>root.handle()
        self._zpool = <libzfs.zpool_handle_t*>pool.handle()
        self._propid = propid
        self.name = libzfs.zpool_prop_to_name(self._propid)

    def __getstate__(self):
        return {
            'value': self.value,
            'source': self.source.name
        }

    property value:
        def __get__(self):
            cdef char cstr[libzfs.ZPOOL_MAXPROPLEN]
            if libzfs.zpool_get_prop(self._zpool, self._propid, cstr, sizeof(cstr), NULL, False) != 0:
                return '-'

            return cstr

        def __set__(self, value):
            if libzfs.zpool_set_prop(self._zpool, self.name, value) != 0:
                raise ZFSException(
                    Error(libzfs.libzfs_errno(self._root)),
                    libzfs.libzfs_error_description(self._root)
                )

    property source:
        def __get__(self):
            cdef zfs.zprop_source_t src
            libzfs.zpool_get_prop(self._zpool, self._propid, NULL, 0, &src, False)
            return PropertySource(src)

    property allowed_values:
        def __get__(self):
            pass

    def reset(self):
        pass


cdef class ZFSProperty(object):
    cdef libzfs.libzfs_handle_t* _root
    cdef libzfs.zfs_handle_t* _dataset
    cdef zfs.zfs_prop_t _propid
    cdef readonly object name

    def __init__(self, ZFS root, ZFSDataset dataset, zfs.zfs_prop_t propid):
        self._root = <libzfs.libzfs_handle_t*>root.handle()
        self._dataset = <libzfs.zfs_handle_t*>dataset.handle()
        self._propid = propid
        self.name = libzfs.zfs_prop_to_name(self._propid)

    def __getstate__(self):
        return {
            'value': self.value,
            'source': self.source.name if self.source else None
        }

    property value:
        def __get__(self):
            cdef char cstr[64]
            if libzfs.zfs_prop_get(self._dataset, self._propid, cstr, 64, NULL, NULL, 0, False) != 0:
                return None

            return cstr

        def __set__(self, value):
            if libzfs.zfs_prop_set(self._dataset, self.name, value) != 0:
                raise ZFSException(
                    Error(libzfs.libzfs_errno(self._root)),
                    libzfs.libzfs_error_description(self._root)
                )


    property source:
        def __get__(self):
            cdef char val[64]
            cdef char cstr[64]
            cdef zfs.zprop_source_t source
            if libzfs.zfs_prop_get(self._dataset, self._propid, val, 64, &source, cstr, 64, False) != 0:
                return None

            return PropertySource(<int>source)

    property allowed_values:
        def __get__(self):
            pass

    def reset(self):
        pass


cdef class ZFSVdev(object):
    cdef readonly ZFSPool zpool
    cdef readonly ZFS root
    cdef readonly object nvlist
    cdef readonly uint64_t guid

    def __init__(self, ZFS root, ZFSPool pool=None, nvlist=None):
        self.root = root
        self.zpool = pool
        self.nvlist = nvlist

        if nvlist:
            self.guid = nvlist['guid']
        else:
            self.guid = 0
            self.nvlist = nvpair.NVList()
            self.nvlist['children'] = []

    def __getstate__(self):
        return {
            'type': self.type,
            'path': self.path,
            'guid': self.guid,
            'status': self.status,
            'children': [i.__getstate__() for i in self.children]
        }

    def add_child_vdev(self, vdev):
        self.nvlist['children'].append(vdev.nvlist)

    property type:
        def __get__(self):
            value = self.nvlist.get('type')
            if value == 'raidz':
                return value + str(self.nvlist.get('nparity'))

            return value

        def __set__(self, value):
            if value not in ('root', 'disk', 'file', 'raidz1', 'raidz2', 'raidz3', 'mirror'):
                raise ValueError('Invalid vdev type')

            if value.startswith('raidz'):
                self.nvlist['type'] = 'raidz'
                self.nvlist['nparity'] = value[-1]

            self.nvlist['type'] = value

    property path:
        def __get__(self):
            return self.nvlist.get('path')

        def __set__(self, value):
            self.nvlist['path'] = value

    property status:
        def __get__(self):
            stats = self.nvlist['vdev_stats']
            return libzfs.zpool_state_to_name(stats[1], stats[2])

    property size:
        def __get__(self):
            return self.nvlist['asize'] << self.nvlist['ashift']

    property children:
        def __get__(self):
            if 'children' not in self.nvlist:
                return

            for i in self.nvlist['children']:
                yield ZFSVdev(self.root, self.zpool, i)

        def __set__(self, value):
            self.nvlist['children'] = [i.nvlist for i in value]

    property disks:
        def __get__(self):
            if self.type == 'disk':
                return [self.path]
            elif self.type == 'file':
                return []
            else:
                result = []
                for i in self.children:
                    result += i.disks

                return result


cdef class ZPoolScrub(object):
    cdef readonly ZFS root
    cdef readonly ZFSPool pool
    cdef readonly object stat

    def __init__(self, ZFS root, ZFSPool pool):
        self.root = root
        self.pool = pool
        self.stat = pool.config['vdev_tree']['scan_stats']

    property state:
        def __get__(self):
            return ScanState(self.stat[1])

    property start_time:
        def __get__(self):
            return datetime.datetime.fromtimestamp(self.stat[2])

    property end_time:
        def __get__(self):
            return datetime.datetime.fromtimestamp(self.stat[3])

    property bytes_to_scan:
        def __get__(self):
            return self.stat[4]

    property bytes_scanned:
        def __get__(self):
            return self.stat[5]

    property errors:
        def __get__(self):
            return self.stat[8]

    property percentage:
        def __get__(self):
            if not self.bytes_to_scan:
                return 0

            return (<float>self.bytes_scanned / <float>self.bytes_to_scan) * 100

    def __getstate__(self):
        return {
            'func': self.stat[0],
            'state': self.state,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'percentage': self.percentage,
            'bytes_to_process': self.bytes_scanned,
            'bytes_processed': self.bytes_to_scan,
            'errors': self.errors
        }


cdef class ZFSPool(object):
    cdef libzfs.zpool_handle_t *_zpool
    cdef readonly ZFS root
    cdef readonly ZFSDataset root_dataset
    cdef readonly object name

    def __init__(self, ZFS root, uintptr_t handle):
        self.root = root
        self._zpool = <libzfs.zpool_handle_t*>handle
        self.name = libzfs.zpool_get_name(self._zpool)
        self.root_dataset = ZFSDataset(
            self.root,
            self,
            <uintptr_t>libzfs.zfs_open(
                <libzfs.libzfs_handle_t*>self.root.handle(),
                self.name,
                zfs.ZFS_TYPE_FILESYSTEM
            )
        )

    def __getstate__(self):
        return {
            'name': self.name,
            'guid': self.guid,
            'hostname': self.hostname,
            'status': self.status,
            'root_dataset': self.root_dataset.__getstate__(),
            'properties': {k: p.__getstate__() for k, p in self.properties.items()},
            'groups': {
                'data': [i.__getstate__() for i in self.data_vdevs],
                'log': [i.__getstate__() for i in self.log_vdevs],
                'cache': [i.__getstate__() for i in self.cache_vdevs]
            },
        }

    cdef uintptr_t handle(self):
        return <uintptr_t>self._zpool

    @staticmethod
    cdef int __iterate_props(int proptype, void* arg):
        proptypes = <object>arg
        proptypes.append(proptype)
        return zfs.ZPROP_CONT

    property data_vdevs:
        def __get__(self):
            for child in self.config['vdev_tree']['children']:
                if not child['is_log']:
                    yield ZFSVdev(self.root, self, child)

    property log_vdevs:
        def __get__(self):
            for child in self.config['vdev_tree']['children']:
                if child['is_log']:
                    yield ZFSVdev(self.root, self, child)

    property cache_vdevs:
        def __get__(self):
            if not 'l2cache' in self.config['vdev_tree']:
                return

            for child in self.config['vdev_tree']['l2cache']:
                yield ZFSVdev(self.root, self, child)

    property groups:
        def __get__(self):
            return {
                'data': list(self.data_vdevs),
                'log': list(self.log_vdevs),
                'cache': list(self.cache_vdevs)
            }

    property guid:
        def __get__(self):
            return self.config['pool_guid']

    property hostname:
        def __get__(self):
            return self.config['hostname']

    property status:
        def __get__(self):
            stats = self.config['vdev_tree']['vdev_stats']
            return libzfs.zpool_state_to_name(stats[1], stats[2])

    property config:
        def __get__(self):
            cdef uintptr_t nvl = <uintptr_t>libzfs.zpool_get_config(self._zpool, NULL)
            return nvpair.NVList(nvl)

    property properties:
        def __get__(self):
            proptypes = []
            libzfs.zprop_iter(self.__iterate_props, <void*>proptypes, True, True, zfs.ZFS_TYPE_POOL)
            return {p.name: p for p in [ZPoolProperty(self.root, self, x) for x in proptypes]}

    property disks:
        def __get__(self):
            result = []
            for g in self.groups.values():
                for v in g:
                    result += v.disks

            return result

    property scrub:
        def __get__(self):
            return ZPoolScrub(self.root, self)

    def create(self, name, fsopts):
        cdef uintptr_t cfsopts = fsopts.handle()
        if libzfs.zfs_create(
            <libzfs.libzfs_handle_t*>self.root.handle(),
            name,
            zfs.ZFS_TYPE_FILESYSTEM,
            <nvpair.nvlist_t*>cfsopts) != 0:
            raise ZFSException(self.root.errno, self.root.errstr)

    def destroy(self, name):
        pass

    def attach_vdev(self, vdev):
        pass

    def delete(self):
        if libzfs.zpool_destroy(self._zpool, "destroy") != 0:
            raise ZFSException(self.root.errno, self.root.errstr)

    def start_scrub(self):
        if libzfs.zpool_scan(self._zpool, zfs.POOL_SCAN_SCRUB) != 0:
            raise ZFSException(self.root.errno, self.root.errstr)

    def stop_scrub(self):
        if libzfs.zpool_scan(self._zpool, zfs.POOL_SCAN_NONE) != 0:
            raise ZFSException(self.root.errno, self.root.errstr)


cdef class ZFSDataset(object):
    cdef libzfs.libzfs_handle_t* _root_handle
    cdef libzfs.zfs_handle_t* _handle
    cdef readonly ZFS root
    cdef readonly ZFSPool pool
    cdef readonly object name

    def __init__(self, ZFS root, ZFSPool pool, uintptr_t handle):
        self.root = root
        self.pool = pool
        self._root_handle = <libzfs.libzfs_handle_t*>self.root.handle()
        self._handle = <libzfs.zfs_handle_t*>handle
        self.name = libzfs.zfs_get_name(self._handle)

    def __getstate__(self):
        return {
            'name': self.name,
            'properties': {k: p.__getstate__() for k, p in self.properties.items()},
            'children': [i.__getstate__() for i in self.children]
        }

    cdef uintptr_t handle(self):
        return <uintptr_t>self._handle

    @staticmethod
    cdef int __iterate_props(int proptype, void* arg):
        proptypes = <object>arg
        proptypes.append(proptype)
        return zfs.ZPROP_CONT

    @staticmethod
    cdef int __iterate_children(libzfs.zfs_handle_t* handle, void *arg):
        datasets = <object>arg
        datasets.append(<uintptr_t>handle)

    @staticmethod
    cdef int __iterate_snapshots(libzfs.zfs_handle_t* handle, void *arg):
        snapshots = <object>arg
        snapshots.append(<uintptr_t>handle)

    property children:
        def __get__(self):
            datasets = []
            libzfs.zfs_iter_children(self._handle, self.__iterate_children, <void*>datasets)
            return [ZFSDataset(self.root, self.pool, h) for h in datasets]

    property snapshots:
        def __get__(self):
            snapshots = []
            libzfs.zfs_iter_children(self._handle, self.__iterate_snapshots, <void*>snapshots)
            return [ZFSSnapshot(self.root, self.pool, h) for h in snapshots]

    property properties:
        def __get__(self):
            proptypes = []
            libzfs.zprop_iter(self.__iterate_props, <void*>proptypes, True, True, zfs.ZFS_TYPE_FILESYSTEM)
            return {p.name: p for p in [ZFSProperty(self.root, self, x) for x in proptypes]}

    def rename(self, new_name):
        pass

    def delete(self):
        if libzfs.zfs_destroy(self._handle, True) != 0:
            raise ZFSException(self.root.errno, self.root.errstr)

    def mount(self):
        if libzfs.zfs_mount(self._handle, NULL, 0) != 0:
            raise ZFSException(self.root.errno, self.root.errstr)

    def umount(self):
        if libzfs.zfs_unmountall(self._handle, 0) != 0:
            raise ZFSException(self.root.errno, self.root.errstr)


cdef class ZFSSnapshot(ZFSDataset):
    pass
