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
import nvpair
cimport libzfs
cimport zfs


cdef class Zfs(object):
    cdef libzfs.libzfs_handle_t *_root

    def __cinit__(self):
        self._root = libzfs.libzfs_init()

    def __dealloc__(self):
        libzfs.libzfs_fini(self._root)

    cdef uintptr_t handle(self):
        return <uintptr_t>self._root

    @staticmethod
    cdef int __iterate_pools(libzfs.zpool_handle_t *handle, void *arg):
        pools = <object>arg
        pools.append(<uintptr_t>handle)

    @property
    def pools(self):
        pools = []
        libzfs.zpool_iter(self._root, self.__iterate_pools, <void *>pools)
        return [ZfsPool(self, h) for h in pools]

    def get(self, name):
        cdef libzfs.zpool_handle_t *handle = libzfs.zpool_open(self._root, name)
        if handle is NULL:
            raise KeyError('Pool {0} not found'.format(name))

        return ZfsPool(self, <uintptr_t>handle)


cdef class ZpoolProperty(object):
    cdef libzfs.libzfs_handle_t* _root
    cdef libzfs.zpool_handle_t* _zpool
    cdef zfs.zpool_prop_t _propid
    cdef readonly object name

    def __init__(self, Zfs root, ZfsPool pool, zfs.zpool_prop_t propid):
        self._root = <libzfs.libzfs_handle_t*>root.handle()
        self._zpool = <libzfs.zpool_handle_t*>pool.handle()
        self._propid = propid
        self.name = libzfs.zpool_prop_to_name(self._propid)

    @property
    def value(self):
        cdef char cstr[256]
        if libzfs.zpool_get_prop(self._zpool, self._propid, cstr, len(cstr), NULL, False) != 0:
            return '-'

        return cstr

    @value.setter
    def value(self, value):
        pass

    @property
    def source(self):
        pass

    @property
    def allowed_values(self):
        pass

    def reset(self):
        pass


cdef class ZfsProperty(object):
    cdef libzfs.libzfs_handle_t* _root
    cdef libzfs.zfs_handle_t* _dataset
    cdef zfs.zfs_prop_t _propid
    cdef readonly object name

    def __init__(self, Zfs root, ZfsDataset dataset, zfs.zfs_prop_t propid):
        self._root = <libzfs.libzfs_handle_t*>root.handle()
        self._dataset = <libzfs.zfs_handle_t*>dataset.handle()
        self._propid = propid
        self.name = libzfs.zfs_prop_to_name(self._propid)

    @property
    def value(self):
        cdef char cstr[64]
        if libzfs.zfs_prop_get(self._dataset, self._propid, cstr, len(cstr), NULL, NULL, 0, False) != 0:
            return '-'

        return cstr

    @value.setter
    def value(self, value):
        pass

    @property
    def source(self):
        pass

    @property
    def allowed_values(self):
        pass

    def reset(self):
        pass


cdef class ZfsVdev(object):
    cdef libzfs.zpool_handle_t *_zpool
    cdef readonly object libzfs
    cdef readonly const char* name
    cdef readonly uint64_t guid

    def __init__(self, Zfs zfs, ZfsPool pool):
        self.libzfs = zfs
        self._zpool = <libzfs.zpool_handle_t*>pool.handle()


cdef class ZfsPoolGroup(object):
    pass


cdef class ZfsPool(object):
    cdef libzfs.zpool_handle_t *_zpool
    cdef readonly Zfs root
    cdef readonly ZfsDataset root_dataset
    cdef readonly const char* name
    cdef readonly uint64_t guid

    def __init__(self, Zfs root, uintptr_t handle):
        self.root = root
        self._zpool = <libzfs.zpool_handle_t*>handle
        self.name = libzfs.zpool_get_name(self._zpool)
        self.root_dataset = ZfsDataset(
            self.root,
            self,
            <uintptr_t>libzfs.zfs_open(
                <libzfs.libzfs_handle_t*>self.root.handle(),
                self.name,
                zfs.ZFS_TYPE_FILESYSTEM
            )
        )

    cdef uintptr_t handle(self):
        return <uintptr_t>self._zpool

    @staticmethod
    cdef int __iterate_props(int proptype, void* arg):
        proptypes = <object>arg
        proptypes.append(proptype)
        return zfs.ZPROP_CONT

    @classmethod
    def by_name(cls, libzfs, name):
        pass

    @property
    def groups(self):
        pass

    @property
    def datasets(self):
        pass

    @property
    def config(self):
        cdef uintptr_t nvl = <uintptr_t>libzfs.zpool_get_config(self._zpool, NULL)
        return nvpair.NVList(nvl)

    def properties(self):
        proptypes = []
        libzfs.zprop_iter(self.__iterate_props, <void*>proptypes, True, True, zfs.ZFS_TYPE_POOL)
        return [ZpoolProperty(self.root, self, x) for x in proptypes]


cdef class ZfsDataset:
    cdef libzfs.libzfs_handle_t* _root_handle
    cdef libzfs.zfs_handle_t* _handle
    cdef readonly Zfs root
    cdef readonly ZfsPool pool
    cdef readonly const char* name

    def __init__(self, Zfs root, ZfsPool pool, uintptr_t handle):
        self.root = root
        self.pool = pool
        self._root_handle = <libzfs.libzfs_handle_t*>self.root.handle()
        self._handle = <libzfs.zfs_handle_t*>handle
        self.name = libzfs.zfs_get_name(self._handle)

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

    def children(self):
        datasets = []
        libzfs.zfs_iter_children(self._handle, self.__iterate_children, <void*>datasets)
        return [ZfsDataset(self.root, self.pool, h) for h in datasets]

    def properties(self):
        proptypes = []
        libzfs.zprop_iter(self.__iterate_props, <void*>proptypes, True, True, zfs.ZFS_TYPE_FILESYSTEM)
        return [ZfsProperty(self.root, self, x) for x in proptypes]