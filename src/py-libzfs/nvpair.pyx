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

cimport nvpair
import collections
import numbers
import enum
from libc.stdint cimport *
from libc.stdlib cimport malloc, free


class NVType(enum.IntEnum):
    DATA_TYPE_UNKNOWN = nvpair.DATA_TYPE_UNKNOWN
    DATA_TYPE_BOOLEAN = nvpair.DATA_TYPE_BOOLEAN
    DATA_TYPE_BYTE = nvpair.DATA_TYPE_BYTE
    DATA_TYPE_INT16 = nvpair.DATA_TYPE_INT16
    DATA_TYPE_UINT16 = nvpair.DATA_TYPE_UINT16
    DATA_TYPE_INT32 = nvpair.DATA_TYPE_INT32
    DATA_TYPE_UINT32 = nvpair.DATA_TYPE_UINT32
    DATA_TYPE_INT64 = nvpair.DATA_TYPE_INT64
    DATA_TYPE_UINT64 = nvpair.DATA_TYPE_UINT64
    DATA_TYPE_STRING = nvpair.DATA_TYPE_STRING
    DATA_TYPE_BYTE_ARRAY = nvpair.DATA_TYPE_BYTE_ARRAY
    DATA_TYPE_INT16_ARRAY = nvpair.DATA_TYPE_INT16_ARRAY
    DATA_TYPE_UINT16_ARRAY = nvpair.DATA_TYPE_UINT16_ARRAY
    DATA_TYPE_INT32_ARRAY = nvpair.DATA_TYPE_INT32_ARRAY
    DATA_TYPE_UINT32_ARRAY = nvpair.DATA_TYPE_UINT32_ARRAY
    DATA_TYPE_INT64_ARRAY = nvpair.DATA_TYPE_INT64_ARRAY
    DATA_TYPE_UINT64_ARRAY = nvpair.DATA_TYPE_UINT64_ARRAY
    DATA_TYPE_STRING_ARRAY = nvpair.DATA_TYPE_STRING_ARRAY
    DATA_TYPE_HRTIME = nvpair.DATA_TYPE_HRTIME
    DATA_TYPE_NVLIST = nvpair.DATA_TYPE_NVLIST
    DATA_TYPE_NVLIST_ARRAY = nvpair.DATA_TYPE_NVLIST_ARRAY
    DATA_TYPE_BOOLEAN_VALUE = nvpair.DATA_TYPE_BOOLEAN_VALUE
    DATA_TYPE_INT8 = nvpair.DATA_TYPE_INT8
    DATA_TYPE_UINT8 = nvpair.DATA_TYPE_UINT8
    DATA_TYPE_BOOLEAN_ARRAY = nvpair.DATA_TYPE_BOOLEAN_ARRAY
    DATA_TYPE_INT8_ARRAY = nvpair.DATA_TYPE_INT8_ARRAY
    DATA_TYPE_UINT8_ARRAY = nvpair.DATA_TYPE_UINT8_ARRAY
    DATA_TYPE_DOUBLE = nvpair.DATA_TYPE_DOUBLE


cdef class NVList(object):
    cdef nvpair.nvlist_t* _nvlist
    cdef int _foreign

    def __init__(self, uintptr_t nvlist=0, otherdict=None):
        if nvlist:
            self._foreign = True
            self._nvlist = <nvpair.nvlist_t*>nvlist
        else:
            self._foreign = False
            nvpair.nvlist_alloc(&self._nvlist, nvpair.NV_UNIQUE_NAME, 0)

        if otherdict:
            for k, v in otherdict.items():
                self[k] = v

    def __dealloc__(self):
        if not self._foreign:
            nvpair.nvlist_free(self._nvlist)

    cpdef uintptr_t handle(self):
        return <uintptr_t>self._nvlist

    cdef nvpair.nvpair_t* __get_pair(self, key) except NULL:
        cdef nvpair.nvpair_t* pair
        if nvpair.nvlist_lookup_nvpair(self._nvlist, key, &pair) != 0:
            raise ValueError('Key {0} not found'.format(key))

        return pair

    cdef object __get_value(self, nvpair.nvpair_t* pair):
        cdef nvpair.nvlist_t *nested
        cdef char *cstr
        cdef void *carray
        cdef uint_t carraylen
        cdef bint boolean
        cdef int32_t cint
        cdef uint64_t clong
        cdef int datatype

        datatype = nvpair.nvpair_type(pair)

        if datatype == nvpair.DATA_TYPE_STRING:
            nvpair.nvpair_value_string(pair, &cstr)
            return cstr

        if datatype == nvpair.DATA_TYPE_BOOLEAN:
            nvpair.nvpair_value_boolean_value(pair, <boolean_t*>&boolean)
            return boolean

        if datatype == nvpair.DATA_TYPE_BYTE:
            nvpair.nvpair_value_byte(pair, <uchar_t*>&cint)
            return cint

        if datatype == nvpair.DATA_TYPE_INT8:
            nvpair.nvpair_value_int8(pair, <int8_t*>&cint)
            return cint

        if datatype == nvpair.DATA_TYPE_UINT8:
            nvpair.nvpair_value_uint8(pair, <uint8_t*>&cint)
            return cint

        if datatype == nvpair.DATA_TYPE_INT16:
            nvpair.nvpair_value_int16(pair, <int16_t*>&cint)
            return cint

        if datatype == nvpair.DATA_TYPE_UINT16:
            nvpair.nvpair_value_uint16(pair, <uint16_t*>&cint)
            return cint

        if datatype == nvpair.DATA_TYPE_INT32:
            nvpair.nvpair_value_int32(pair, <int32_t*>&cint)
            return cint

        if datatype == nvpair.DATA_TYPE_UINT32:
            nvpair.nvpair_value_uint32(pair, <uint32_t*>&clong)
            return clong

        if datatype == nvpair.DATA_TYPE_INT64:
            nvpair.nvpair_value_int64(pair, <int64_t*>&clong)
            return clong

        if datatype == nvpair.DATA_TYPE_UINT64:
            nvpair.nvpair_value_uint64(pair, <uint64_t*>&clong)
            return clong

        if datatype == nvpair.DATA_TYPE_BYTE_ARRAY:
            nvpair.nvpair_value_byte_array(pair, <uchar_t**>&carray, &carraylen)
            return [x for x in (<uchar_t *>carray)[:carraylen]]

        if datatype == nvpair.DATA_TYPE_INT8_ARRAY:
            nvpair.nvpair_value_int8_array(pair, <int8_t**>&carray, &carraylen)
            return [x for x in (<uint8_t *>carray)[:carraylen]]

        if datatype == nvpair.DATA_TYPE_UINT8_ARRAY:
            nvpair.nvpair_value_uint8_array(pair, <uint8_t**>&carray, &carraylen)
            return [x for x in (<uint8_t *>carray)[:carraylen]]

        if datatype == nvpair.DATA_TYPE_INT16_ARRAY:
            nvpair.nvpair_value_int16_array(pair, <int16_t**>&carray, &carraylen)
            return [x for x in (<int16_t *>carray)[:carraylen]]

        if datatype == nvpair.DATA_TYPE_UINT16_ARRAY:
            nvpair.nvpair_value_uint16_array(pair, <uint16_t**>&carray, &carraylen)
            return [x for x in (<uint16_t *>carray)[:carraylen]]

        if datatype == nvpair.DATA_TYPE_INT32_ARRAY:
            nvpair.nvpair_value_int32_array(pair, <int32_t**>&carray, &carraylen)
            return [x for x in (<int32_t *>carray)[:carraylen]]

        if datatype == nvpair.DATA_TYPE_UINT32_ARRAY:
            nvpair.nvpair_value_uint32_array(pair, <uint32_t**>&carray, &carraylen)
            return [x for x in (<uint32_t *>carray)[:carraylen]]

        if datatype == nvpair.DATA_TYPE_INT64_ARRAY:
            nvpair.nvpair_value_int64_array(pair, <int64_t**>&carray, &carraylen)
            return [x for x in (<int64_t *>carray)[:carraylen]]

        if datatype == nvpair.DATA_TYPE_UINT64_ARRAY:
            nvpair.nvpair_value_uint64_array(pair, <uint64_t**>&carray, &carraylen)
            return [x for x in (<uint64_t *>carray)[:carraylen]]

        if datatype == nvpair.DATA_TYPE_STRING_ARRAY:
            nvpair.nvpair_value_string_array(pair, <char***>&carray, &carraylen)
            return [x for x in (<char**>carray)[:carraylen]]

        if datatype == nvpair.DATA_TYPE_NVLIST:
            nvpair.nvpair_value_nvlist(pair, &nested)
            return NVList(<uintptr_t>nested)

        if datatype == nvpair.DATA_TYPE_NVLIST_ARRAY:
            nvpair.nvpair_value_nvlist_array(pair, <nvpair.nvlist_t***>&carray, &carraylen)
            return [NVList(x) for x in (<uintptr_t *>carray)[:carraylen]]

    def __contains__(self, key):
        return nvpair.nvlist_exists(self._nvlist, key)

    def __delitem__(self, key):
        nvpair.nvlist_remove(self._nvlist, key, self.type(key))

    def __iter__(self):
        cdef nvpair.nvpair_t *pair = NULL
        while True:
            pair = nvpair.nvlist_next_nvpair(self._nvlist, pair)
            if pair is NULL:
                return

            yield nvpair.nvpair_name(pair)

    def get(self, str key, object default=None):
        if not key in self:
            return default

        return self[key]

    def type(self, str key):
        cdef nvpair.nvpair_t *pair = self.__get_pair(key)
        return nvpair.nvpair_type(pair)

    def set(self, str key, object value, int typeid):
        cdef NVList cnvlist
        cdef void* carray = NULL
        cdef uintptr_t cptr

        # Oh god, this is tedious...

        if isinstance(value, (str, unicode)):
            if typeid == nvpair.DATA_TYPE_STRING:
                nvpair.nvlist_add_string(self._nvlist, key, value)
                return

        if isinstance(value, bool):
            if typeid == nvpair.DATA_TYPE_BOOLEAN:
                nvpair.nvlist_add_boolean_value(self._nvlist, key, <boolean_t>value)
                return

        if isinstance(value, numbers.Number):
            if typeid == nvpair.DATA_TYPE_BYTE:
                nvpair.nvlist_add_byte(self._nvlist, key, <char>value)
                return

            if typeid == nvpair.DATA_TYPE_UINT8:
                nvpair.nvlist_add_uint8(self._nvlist, key, <uint8_t>value)
                return

            if typeid == nvpair.DATA_TYPE_INT8:
                nvpair.nvlist_add_int8(self._nvlist, key, <int8_t>value)
                return

            if typeid == nvpair.DATA_TYPE_UINT16:
                nvpair.nvlist_add_uint16(self._nvlist, key, <uint16_t>value)
                return

            if typeid == nvpair.DATA_TYPE_INT16:
                nvpair.nvlist_add_int16(self._nvlist, key, <int16_t>value)
                return

            if typeid == nvpair.DATA_TYPE_UINT32:
                nvpair.nvlist_add_uint32(self._nvlist, key, <uint32_t>value)
                return

            if typeid == nvpair.DATA_TYPE_INT32:
                nvpair.nvlist_add_int32(self._nvlist, key, <int32_t>value)
                return

            if typeid == nvpair.DATA_TYPE_UINT64:
                nvpair.nvlist_add_uint64(self._nvlist, key, <uint64_t>value)
                return

            if typeid == nvpair.DATA_TYPE_INT64:
                nvpair.nvlist_add_int64(self._nvlist, key, <int64_t>value)
                return

        if isinstance(value, NVList):
            if typeid == nvpair.DATA_TYPE_NVLIST:
                cnvlist = <NVList>value
                cptr = cnvlist.handle()
                nvpair.nvlist_add_nvlist(self._nvlist, key, <nvpair.nvlist_t*>cptr)
                return

        if isinstance(value, collections.Sequence):
            if typeid == nvpair.DATA_TYPE_STRING_ARRAY:
                carray = malloc(len(value) * sizeof(char*))
                for idx, i in enumerate(value):
                    (<char**>carray)[idx] = i

                nvpair.nvlist_add_string_array(self._nvlist, key, <char**>carray, len(value))

            if typeid == nvpair.DATA_TYPE_BOOLEAN_ARRAY:
                carray = malloc(len(value) * sizeof(char*))
                for idx, i in enumerate(value):
                    (<boolean_t*>carray)[idx] = i

                nvpair.nvlist_add_boolean_array(self._nvlist, key, <boolean_t*>carray, len(value))

            if typeid == nvpair.DATA_TYPE_BYTE_ARRAY:
                carray = malloc(len(value) * sizeof(char))
                for idx, i in enumerate(value):
                    (<char*>carray)[idx] = i

                nvpair.nvlist_add_byte_array(self._nvlist, key, <uchar_t*>carray, len(value))

            if typeid == nvpair.DATA_TYPE_UINT8_ARRAY:
                carray = malloc(len(value) * sizeof(uint8_t))
                for idx, i in enumerate(value):
                    (<uint8_t*>carray)[idx] = i

                nvpair.nvlist_add_uint8_array(self._nvlist, key, <uint8_t*>carray, len(value))

            if typeid == nvpair.DATA_TYPE_INT8_ARRAY:
                carray = malloc(len(value) * sizeof(int8_t))
                for idx, i in enumerate(value):
                    (<int8_t*>carray)[idx] = i

                nvpair.nvlist_add_int8_array(self._nvlist, key, <int8_t*>carray, len(value))

            if typeid == nvpair.DATA_TYPE_UINT16_ARRAY:
                carray = malloc(len(value) * sizeof(uint16_t))
                for idx, i in enumerate(value):
                    (<uint16_t*>carray)[idx] = i

                nvpair.nvlist_add_uint16_array(self._nvlist, key, <uint16_t*>carray, len(value))

            if typeid == nvpair.DATA_TYPE_INT16_ARRAY:
                carray = malloc(len(value) * sizeof(int16_t))
                for idx, i in enumerate(value):
                    (<uint16_t*>carray)[idx] = i


                nvpair.nvlist_add_int16_array(self._nvlist, key, <int16_t*>carray, len(value))

            if typeid == nvpair.DATA_TYPE_UINT32_ARRAY:
                carray = malloc(len(value) * sizeof(uint32_t))
                for idx, i in enumerate(value):
                    (<uint32_t*>carray)[idx] = i

                nvpair.nvlist_add_uint32_array(self._nvlist, key, <uint32_t*>carray, len(value))

            if typeid == nvpair.DATA_TYPE_INT32_ARRAY:
                carray = malloc(len(value) * sizeof(int32_t))
                for idx, i in enumerate(value):
                    (<int32_t*>carray)[idx] = i

                nvpair.nvlist_add_int32_array(self._nvlist, key, <int32_t*>carray, len(value))

            if typeid == nvpair.DATA_TYPE_UINT64_ARRAY:
                carray = malloc(len(value) * sizeof(uint64_t))
                for idx, i in enumerate(value):
                    (<uint64_t*>carray)[idx] = i

                nvpair.nvlist_add_uint64_array(self._nvlist, key, <uint64_t*>carray, len(value))

            if typeid == nvpair.DATA_TYPE_INT64_ARRAY:
                carray = malloc(len(value) * sizeof(int64_t))
                for idx, i in enumerate(value):
                    (<int64_t*>carray)[idx] = i

                nvpair.nvlist_add_int64_array(self._nvlist, key, <int64_t*>carray, len(value))

            if typeid == nvpair.DATA_TYPE_NVLIST_ARRAY:
                carray = malloc(len(value) * sizeof(nvpair.nvlist_t*))
                for idx, i in enumerate(value):
                    cnvlist = <NVList>i
                    cptr = cnvlist.handle()
                    (<uintptr_t*>carray)[idx] = cptr

                nvpair.nvlist_add_nvlist_array(self._nvlist, key, <nvpair.nvlist_t**>carray, len(value))

            if carray != NULL:
                free(carray)

            return

        raise ValueError('Value not compatible with type specified')

    def __getitem__(self, str key):
        cdef nvpair.nvpair_t *pair

        pair = self.__get_pair(key)
        return self.__get_value(pair)

    def __setitem__(self, key, value):
        if type(value) is bool:
            self.set(key, value, nvpair.DATA_TYPE_BOOLEAN)

        if type(value) is int:
            self.set(key, value, nvpair.DATA_TYPE_UINT32)

        if type(value) is long:
            self.set(key, value, nvpair.DATA_TYPE_UINT64)

        if type(value) is str or type(value) is unicode:
            self.set(key, value, nvpair.DATA_TYPE_STRING)

        if type(value) is NVList:
            self.set(key, value, nvpair.DATA_TYPE_NVLIST)

        if type(value) is list:
            # We need some heuristics here...
            if len(value) == 0:
                # don't know what to do!
                return

            if type(value[0]) is NVList:
                self.set(key, value, nvpair.DATA_TYPE_NVLIST_ARRAY)

            if type(value[0]) is int:
                self.set(key, value, nvpair.DATA_TYPE_INT32_ARRAY)

            if type(value[0]) is long:
                self.set(key, value, nvpair.DATA_TYPE_INT64_ARRAY)

            if type(value[0]) is str:
                self.set(key, value, nvpair.DATA_TYPE_STRING_ARRAY)

    def get_type(self, key):
        pair = self.__get_pair(key)
        return nvpair.nvpair_type(pair)

    def keys(self):
        return list(self)

    def values(self):
        return [v for k, v in self.items()]

    def items(self):
        cdef nvpair.nvpair_t *pair = NULL
        while True:
            pair = nvpair.nvlist_next_nvpair(self._nvlist, pair)
            if pair is NULL:
                return

            yield (nvpair.nvpair_name(pair), self.__get_value(pair))