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
import nvpair
cimport nvpair
cimport libzfs
cimport zfs


class Error(enum.IntEnum):
    EZFSSUCCESS = libzfs.SUCCESS
    EZFSNOMEM = libzfs.NOMEM
    EZFSBADPROP = libzfs.BADPROP
    EZFSPROPREADONLY = libzfs.PROPREADONLY
    EZFSPROPTYPE = libzfs.PROPTYPE
    EZFSPROPNONINHERIT = libzfs.PROPNONINHERIT
    EZFSPROPSPACE = libzfs.PROPSPACE
    EZFSBADTYPE = libzfs.BADTYPE
    EZFSBUSY = libzfs.BUSY
    EZFSEXISTS = libzfs.EXISTS
    EZFSNOENT = libzfs.NOENT
    EZFSBADSTREAM = libzfs.BADSTREAM
    EZFSDSREADONLY = libzfs.DSREADONLY
    EZFSVOLTOOBIG = libzfs.VOLTOOBIG
    EZFSINVALIDNAME = libzfs.INVALIDNAME
    EZFSBADRESTORE = libzfs.BADRESTORE
    EZFSBADBACKUP = libzfs.BADBACKUP
    EZFSBADTARGET = libzfs.BADTARGET
    EZFSNODEVICE = libzfs.NODEVICE
    EZFSBADDEV = libzfs.BADDEV
    EZFSNOREPLICAS = libzfs.NOREPLICAS
    EZFSRESILVERING = libzfs.RESILVERING
    EZFSBADVERSION = libzfs.BADVERSION
    EZFSPOOLUNAVAIL = libzfs.POOLUNAVAIL
    EZFSDEVOVERFLOW = libzfs.DEVOVERFLOW
    EZFSBADPATH = libzfs.BADPATH
    EZFSCROSSTARGET = libzfs.CROSSTARGET
    EZFSZONED = libzfs.ZONED
    EZFSMOUNTFAILED = libzfs.MOUNTFAILED
    EZFSUMOUNTFAILED = libzfs.UMOUNTFAILED
    EZFSUNSHARENFSFAILED = libzfs.UNSHARENFSFAILED
    EZFSSHARENFSFAILED = libzfs.SHARENFSFAILED
    EZFSPERM = libzfs.PERM
    EZFSNOSPC = libzfs.NOSPC
    EZFSFAULT = libzfs.FAULT
    EZFSIO = libzfs.IO
    EZFSINTR = libzfs.INTR
    EZFSISSPARE = libzfs.ISSPARE
    EZFSINVALCONFIG = libzfs.INVALCONFIG
    EZFSRECURSIVE = libzfs.RECURSIVE
    EZFSNOHISTORY = libzfs.NOHISTORY
    EZFSPOOLPROPS = libzfs.POOLPROPS
    EZFSPOOL_NOTSUP = libzfs.POOL_NOTSUP
    EZFSPOOL_INVALARG = libzfs.POOL_INVALARG
    EZFSNAMETOOLONG = libzfs.NAMETOOLONG
    EZFSOPENFAILED = libzfs.OPENFAILED
    EZFSNOCAP = libzfs.NOCAP
    EZFSLABELFAILED = libzfs.LABELFAILED
    EZFSBADWHO = libzfs.BADWHO
    EZFSBADPERM = libzfs.BADPERM
    EZFSBADPERMSET = libzfs.BADPERMSET
    EZFSNODELEGATION = libzfs.NODELEGATION
    EZFSUNSHARESMBFAILED = libzfs.UNSHARESMBFAILED
    EZFSSHARESMBFAILED = libzfs.SHARESMBFAILED
    EZFSBADCACHE = libzfs.BADCACHE
    EZFSISL2CACHE = libzfs.ISL2CACHE
    EZFSVDEVNOTSUP = libzfs.VDEVNOTSUP
    EZFSNOTSUP = libzfs.NOTSUP
    EZFSACTIVE_SPARE = libzfs.ACTIVE_SPARE
    EZFSUNPLAYED_LOGS = libzfs.UNPLAYED_LOGS
    EZFSREFTAG_RELE = libzfs.REFTAG_RELE
    EZFSREFTAG_HOLD = libzfs.REFTAG_HOLD
    EZFSTAGTOOLONG = libzfs.TAGTOOLONG
    EZFSPIPEFAILED = libzfs.PIPEFAILED
    EZFSTHREADCREATEFAILED = libzfs.THREADCREATEFAILED
    EZFSPOSTSPLIT_ONLINE = libzfs.POSTSPLIT_ONLINE
    EZFSSCRUBBING = libzfs.SCRUBBING
    EZFSNO_SCRUB = libzfs.NO_SCRUB
    EZFSDIFF = libzfs.DIFF
    EZFSDIFFDATA = libzfs.DIFFDATA
    EZFSPOOLREADONLY = libzfs.POOLREADONLY
    EZFSUNKNOWN = libzfs.UNKNOWN


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


cdef class ZFS(object):
    cdef libzfs.libzfs_handle_t *_root

    def __cinit__(self):
        self._root = libzfs.libzfs_init()

    def __dealloc__(self):
        libzfs.libzfs_fini(self._root)

    cdef uintptr_t handle(self):
        return <uintptr_t>self._root

    def __getstate__(self):
        return {p.name: p.__getstate__() for p in self.pools}

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

    @property
    def pools(self):
        pools = []
        libzfs.zpool_iter(self._root, self.__iterate_pools, <void *>pools)
        return [ZFSPool(self, h) for h in pools]

    def get(self, name):
        cdef libzfs.zpool_handle_t *handle = libzfs.zpool_open(self._root, name)
        if handle == NULL:
            raise KeyError('Pool {0} not found'.format(name))

        return ZFSPool(self, <uintptr_t>handle)

    def create(self, name, topology, opts, fsopts):
        root = self.__make_vdev_tree(topology)
        cdef uintptr_t croot = root.nvlist.handle()
        cdef uintptr_t copts = opts.handle()
        cdef uintptr_t cfsopts = fsopts.handle()

        libzfs.zpool_create(
            self._root,
            name,
            <nvpair.nvlist_t*>croot,
            <nvpair.nvlist_t*>copts,
            <nvpair.nvlist_t*>cfsopts)

    def destroy(self, name):
        pass


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

    property value:
        def __get__(self):
            cdef char cstr[libzfs.ZPOOL_MAXPROPLEN]
            if libzfs.zpool_get_prop(self._zpool, self._propid, cstr, sizeof(cstr), NULL, False) != 0:
                return '-'

            return cstr

        def __set__(self, value):
            pass

    property source:
        def __get__(self):
            cdef zfs.zprop_source_t src
            libzfs.zpool_get_prop(self._zpool, self._propid, NULL, 0, &src, False)
            return src

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

    property value:
        def __get__(self):
            cdef char cstr[64]
            if libzfs.zfs_prop_get(self._dataset, self._propid, cstr, 64, NULL, NULL, 0, False) != 0:
                return '-'

            return cstr

        def __set__(self, value):
            pass

    property source:
        def __get__(self):
            pass

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
            'children': [i.__getstate__() for i in self.children]
        }

    def add_child_vdev(self, vdev):
        self.nvlist['children'].append(vdev.nvlist)

    property type:
        def __get__(self):
            return self.nvlist.get('type')

        def __set__(self, value):
            if value not in ('root', 'disk', 'file', 'raidz', 'raidz2', 'raidz3', 'mirror'):
                raise ValueError('Invalid vdev type')

            self.nvlist['type'] = value

    property path:
        def __get__(self):
            return self.nvlist.get('path')

        def __set__(self, value):
            self.nvlist['path'] = value

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


cdef class ZPoolScrub(object):
    cdef readonly ZFS root
    cdef readonly ZFSPool pool

    def __init__(self, ZFS root, ZFSPool pool):
        self.root = root
        self.pool = pool

    def __getstate__(self):
        return {

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
            'root_dataset': self.root_dataset.__getstate__(),
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

    property config:
        def __get__(self):
            cdef uintptr_t nvl = <uintptr_t>libzfs.zpool_get_config(self._zpool, NULL)
            return nvpair.NVList(nvl)

    property properties:
        def __get__(self):
            proptypes = []
            libzfs.zprop_iter(self.__iterate_props, <void*>proptypes, True, True, zfs.ZFS_TYPE_POOL)
            return [ZPoolProperty(self.root, self, x) for x in proptypes]

    property scrub:
        def __get__(self):
            return ZPoolScrub(self.root, self)

    def create(self, name, fsopts):
        pass

    def destroy(self, name):
        pass

    def attach_vdev(self, vdev):
        pass


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

    property children:
        def __get__(self):
            datasets = []
            libzfs.zfs_iter_children(self._handle, self.__iterate_children, <void*>datasets)
            return [ZFSDataset(self.root, self.pool, h) for h in datasets]

    property properties:
        def __get__(self):
            proptypes = []
            libzfs.zprop_iter(self.__iterate_props, <void*>proptypes, True, True, zfs.ZFS_TYPE_FILESYSTEM)
            return [ZFSProperty(self.root, self, x) for x in proptypes]

    def rename(self, new_name):
        pass

    def start_scrub(self):
        pass

    def stop_scrub(self):
        pass

    def mount(self):
        libzfs.zfs_mount(self._handle, NULL, 0)

    def umount(self):
        libzfs.zfs_unmountall(self._handle, 0)


cdef class ZFSSnapshot(object):
    cdef readonly ZFS root
    cdef readonly ZFSPool pool
    cdef readonly object name

    def __init__(self, ZFS root, ZFSPool pool):
        pass