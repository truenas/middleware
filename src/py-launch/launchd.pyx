#+
# Copyright 2015 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

import enum
import os
import socket
from libc.errno cimport errno
from libc.stdint cimport uintptr_t
cimport defs


class ItemType(enum.IntEnum):
    UNKNOWN = 0
    DICTIONARY = defs.LAUNCH_DATA_DICTIONARY
    ARRAY = defs.LAUNCH_DATA_ARRAY
    FD = defs.LAUNCH_DATA_FD
    INTEGER = defs.LAUNCH_DATA_INTEGER
    REAL = defs.LAUNCH_DATA_REAL
    BOOL = defs.LAUNCH_DATA_BOOL
    STRING = defs.LAUNCH_DATA_STRING
    OPAQUE = defs.LAUNCH_DATA_OPAQUE
    ERRNO = defs.LAUNCH_DATA_ERRNO
    MACHPORT = defs.LAUNCH_DATA_MACHPORT


cdef class Item(object):
    cdef defs.launch_data_t _value
    cdef object _refs

    def __init__(self, value=None, uintptr_t ptr=0, typ=None):
        self._refs = []
        self._value = NULL

        if ptr:
            self._value = <defs.launch_data_t>ptr

        if typ is not None and value is None:
            self._value = defs.launch_data_alloc(typ.value)

        if value is not None:
            if type(value) is Item:
                self._value = defs.launch_data_copy(<defs.launch_data_t><uintptr_t>value.ptr)

            if type(value) is int or type(value) is long:
                if typ:
                    if typ == ItemType.INTEGER:
                        self._value = defs.launch_data_new_integer(value)

                    if typ == ItemType.FD:
                        self._value = defs.launch_data_new_fd(value)

                    if typ == ItemType.MACHPORT:
                        self._value = defs.launch_data_new_machport(value)
                else:
                    self._value = defs.launch_data_new_integer(value)

            if type(value) is bool:
                self._value = defs.launch_data_new_bool(value)

            if type(value) is float:
                self._value = defs.launch_data_new_real(value)

            if type(value) is str or type(value) is unicode:
                self._value = defs.launch_data_new_string(value)

            if type(value) is list:
                self._value = defs.launch_data_alloc(defs.LAUNCH_DATA_ARRAY)
                for i in value:
                    self.append(i)

            if type(value) is dict:
                self._value = defs.launch_data_alloc(defs.LAUNCH_DATA_DICTIONARY)
                self.update(value)

        if self._value == NULL:
            raise NotImplementedError(
                'Value {0} of type {1} cannot be converted to launch data item'.format(value, type(value)))

    def __int__(self):
        return int(self.value)

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "<item '{0}', type {1}>".format(self.value, self.type.name)

    def __contains__(self, item):
        cdef uintptr_t ptr

        if self.type == ItemType.DICTIONARY:
            ptr=<uintptr_t>defs.launch_data_dict_lookup(self._value, item)
            return ptr != 0

        raise NotImplementedError('Primitive types doesn\'t support indexing')

    def __getitem__(self, item):
        cdef uintptr_t ptr

        if self.type == ItemType.ARRAY:
            if item >= len(self):
                raise IndexError('list index out of range')

            ptr=<uintptr_t>defs.launch_data_array_get_index(self._value, item)
            if ptr == 0:
                raise KeyError(item)

            return Item(ptr=ptr)

        if self.type == ItemType.DICTIONARY:
            ptr=<uintptr_t>defs.launch_data_dict_lookup(self._value, item)
            if ptr == 0:
                raise KeyError(item)

            return Item(ptr=ptr)

        raise NotImplementedError('Primitive types doesn\'t support indexing')

    def __setitem__(self, key, value):
        if self.type == ItemType.ARRAY:
            item = Item(value)
            self._refs.append(item)
            defs.launch_data_array_set_index(self._value, item._value, key)
            return

        if self.type == ItemType.DICTIONARY:
            item = Item(value)
            self._refs.append(item)
            defs.launch_data_dict_insert(self._value, item._value, key)
            return

        raise NotImplementedError('Primitive types doesn\'t support indexing')

    def __iadd__(self, other):
        if self.type == ItemType.ARRAY:
            for i in other:
                self.append(i)

            return self

        raise NotImplementedError('Not supported for this type')

    property ptr:
        def __get__(self):
            return <uintptr_t>self._value

    property value:
        def __get__(self):
            if self.type == ItemType.INTEGER:
                return defs.launch_data_get_integer(self._value)

            if self.type == ItemType.BOOL:
                return defs.launch_data_get_bool(self._value)

            if self.type == ItemType.REAL:
                return defs.launch_data_get_real(self._value)

            if self.type == ItemType.STRING:
                return defs.launch_data_get_string(self._value)

            if self.type == ItemType.OPAQUE:
                return (<char*>defs.launch_data_get_opaque(self._value))[defs.launch_data_get_opaque_size(self._value):]

            if self.type == ItemType.FD:
                return defs.launch_data_get_fd(self._value)

            if self.type == ItemType.MACHPORT:
                return defs.launch_data_get_machport(self._value)

            if self.type == ItemType.ERRNO:
                return defs.launch_data_get_errno(self._value)

            if self.type == ItemType.ARRAY:
                return list(self)

            if self.type == ItemType.DICTIONARY:
                return dict(self.items())

        def __set__(self, value):
            t = defs.launch_data_get_type(self._value)

            if t == defs.LAUNCH_DATA_INTEGER:
                defs.launch_data_set_integer(self._value, value)

            if t == defs.LAUNCH_DATA_FD:
                defs.launch_data_set_fd(self._value, value)

            if t == defs.LAUNCH_DATA_MACHPORT:
                defs.launch_data_set_machport(self._value, value)

            if t == defs.LAUNCH_DATA_BOOL:
                defs.launch_data_set_bool(self._value, value)

            if t == defs.LAUNCH_DATA_STRING:
                defs.launch_data_set_string(self._value, value)

    property type:
        def __get__(self):
            return ItemType(defs.launch_data_get_type(self._value))

    def keys(self):
        if self.type != ItemType.DICTIONARY:
            raise NotImplementedError('Not a dictionary')

        keys = []
        defs.launch_data_dict_iterate(self._value, self.__iterator, <void*>keys)
        return keys

    def items(self):
        if self.type != ItemType.DICTIONARY:
            raise NotImplementedError('Not a dictionary')

        for i in self.keys():
            yield (i, self[i])

    def get(self, indice, default=None):
        if isinstance(indice, basestring) and self.type == ItemType.DICTIONARY:
            if indice in self:
                return self[indice].value

            return default

        if isinstance(indice, (int, long)) and self.type == ItemType.ARRAY:
            if indice in self:
                return self[indice].value

            return default

        raise NotImplementedError('Unsupported for that item type')

    def append(self, value):
        if self.type != ItemType.ARRAY:
            raise NotImplementedError('Not an array')

        self[len(self)] = value

    def update(self, d):
        for k, v in d.items():
            self[k] = Item(v)

    def __len__(self):
        if self.type == ItemType.ARRAY:
            return defs.launch_data_array_get_count(self._value)

        if self.type == ItemType.DICTIONARY:
            return defs.launch_data_dict_get_count(self._value)

        return len(self.value)

    @staticmethod
    cdef void __iterator(const defs.launch_data_t dict, const char* name, void* data):
        arr = <object>data
        arr.append(name)


cdef class Launchd(object):
    def __init__(self):
        pass

    def message(self, Item data):
        cdef uintptr_t resp
        with nogil:
            resp = <uintptr_t>defs.launch_msg(data._value)

        if resp == 0:
            if errno != 0:
                raise OSError(errno, os.strerror(errno))

            return None

        return Item(ptr=resp)

    def create_sockets(self, plist):
        passive = plist.get('SockPassive', True)
        pathname = plist.get('SockPathName', None)
        st_str = plist.get('SockType', '').lower()
        st = socket.SOCK_STREAM
        family = socket.AF_INET
        proto = socket.IPPROTO_TCP

        if st_str == 'stream':
            st = socket.SOCK_STREAM
        elif st_str == 'dgram':
            st = socket.SOCK_DGRAM
        elif st_str == 'seqpacket':
            st = socket.SOCK_SEQPACKET

        if pathname:
            sock = socket.socket(socket.AF_UNIX, st)

            if passive:
                try:
                    os.remove(pathname)
                except OSError:
                    pass

                sock.bind(pathname)
                yield sock
        else:
            if plist.get('SockProtocol') == 'TCP':
                proto = socket.IPPROTO_TCP
            elif plist.get('SockProtocol') == 'UDP':
                proto = socket.IPPROTO_UDP

            if plist.get('SockFamily') == 'IPv4':
                family = socket.AF_INET
            elif plist.get('SockFamily') == 'IPv6':
                family = socket.AF_INET6

            ai_ret = socket.getaddrinfo(
                plist.get('SockNodeName'),
                plist.get('SockServiceName'),
                family,
                st,
                proto)

            for ai in ai_ret:
                ai_family, ai_socktype, ai_proto, ai_canon, ai_addr = ai
                sock = socket.socket(ai_family, ai_socktype, ai_proto)

                if passive:
                    sock.bind(ai_addr)

                    if ai_socktype in (socket.SOCK_STREAM, socket.SOCK_SEQPACKET):
                        sock.listen(-1)
                else:
                    sock.connect(ai_addr)

                yield sock

    def convert_sockets(self, plist):
        sockets = []
        result = Item(typ=ItemType.DICTIONARY)
        for k, v in plist.items():
            arr = Item(typ=ItemType.ARRAY)
            if v.type == ItemType.ARRAY:
                for i in v:
                    s = list(self.create_sockets(i))
                    sockets += s
                    arr += map(lambda x: Item(value=x.fileno(), typ=ItemType.FD), s)

            if v.type == ItemType.DICTIONARY:
                    s = list(self.create_sockets(v))
                    sockets += s
                    arr += map(lambda x: Item(value=x.fileno(), typ=ItemType.FD), s)

            result[k] = arr

        return sockets, result

    property jobs:
        def __get__(self):
            msg = Item("GetJobs")
            return self.message(msg)

    def load(self, plist):
        sockets = []
        plist = Item(plist)
        if 'Sockets' in plist:
            sockets, result = self.convert_sockets(plist['Sockets'])
            plist['Sockets'] = result

        msg = Item({"SubmitJob": plist})
        reply = self.message(msg)
        if reply.value != 0:
            raise OSError(reply.value, os.strerror(reply.value))

    def unload(self, label):
        msg = Item({"RemoveJob": label})
        reply = self.message(msg)
        if reply.value != 0:
            raise OSError(reply.value, os.strerror(reply.value))

    def start(self, label):
        msg = Item({"StartJob": label})
        reply = self.message(msg)
        if reply.value != 0:
            raise OSError(reply.value, os.strerror(reply.value))

    def stop(self, label):
        msg = Item({"StopJob": label})
        reply = self.message(msg)
        if reply.value != 0:
            raise OSError(reply.value, os.strerror(reply.value))

    def checkin(self):
        msg = Item("CheckIn")
        return self.message(msg)
