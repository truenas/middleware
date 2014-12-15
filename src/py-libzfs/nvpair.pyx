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
from libc.stdint cimport *
from libc.stdlib cimport free

cdef class NVList(object):
	cdef nvpair.nvlist_t* _nvlist
	cdef int _foreign

	def __init__(self, uintptr_t nvlist=0):
		if nvlist != 0:
			self._foreign = True
			self._nvlist = <nvpair.nvlist_t*>nvlist
		else:
			self._foreign = False
			nvpair.nvlist_alloc(&self._nvlist, nvpair.NV_UNIQUE_NAME, 0)

	def __dealloc__(self):
		if not self._foreign:
			nvpair.nvlist_free(self._nvlist)

	cdef nvpair.nvpair_t* __get_pair(self, key):
		cdef nvpair.nvpair_t *pair

		if nvpair.nvlist_lookup_nvpair(self._nvlist, key, &pair) != 0:
			raise KeyError('Key {0} not found'.format(key))

		return pair

	def __contains__(self, key):
		return nvpair.nvlist_exists(self._nvlist, key)

	def __iter__(self):
		cdef nvpair.nvpair_t *pair = NULL

		while True:
			pair = nvpair.nvlist_next_nvpair(self._nvlist, pair)
			if pair is NULL:
				return

			yield nvpair.nvpair_name(pair)

	def __getitem__(self, key):
		cdef nvpair.nvpair_t *pair
		cdef nvpair.nvlist_t *nested
		cdef char *cstr
		cdef void *carray
		cdef uint_t carraylen
		cdef int32_t cint
		cdef uint64_t clong
		cdef int datatype

		pair = self.__get_pair(key)
		datatype = nvpair.nvpair_type(pair)

		if datatype == nvpair.DATA_TYPE_STRING:
			nvpair.nvpair_value_string(pair, &cstr)
			result = <bytes>cstr
			free(cstr)
			return result

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

		if datatype == nvpair.DATA_TYPE_NVLIST:
			nvpair.nvpair_value_nvlist(pair, &nested)
			return NVList(<uintptr_t>nested)

		if datatype == nvpair.DATA_TYPE_NVLIST_ARRAY:
			nvpair.nvpair_value_nvlist_array(pair, <nvpair.nvlist_t***>&carray, &carraylen)
			return [NVList(x) for x in (<uintptr_t *>carray)[:carraylen]]

	def __setitem__(self, key, value):
		if type(value) is int:
			nvpair.nvlist_add_int32(self._nvlist, key, value)

		if type(value) is long:
			nvpair.nvlist_add_int64(self._nvlist, key, value)

		if type(value) is str:
			nvpair.nvlist_add_string(self._nvlist, key, value)


	def get_type(self, key):
		pair = self.__get_pair(key)
		return nvpair.nvpair_type(pair)

	def items(self):
		cdef nvpair.nvpair_t *pair
		
		for key in self:
			pair = self.__get_pair(key)
			yield (key, self[key])	
