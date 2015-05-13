# Copyright 2014 iXsystems, Inc.
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

cdef extern from "launch.h":
    ctypedef int bool
    ctypedef int mach_port_t
    ctypedef struct _launch_data:
        pass

    ctypedef _launch_data* launch_data_t

    ctypedef enum launch_data_type_t:
        LAUNCH_DATA_DICTIONARY
        LAUNCH_DATA_ARRAY
        LAUNCH_DATA_FD
        LAUNCH_DATA_INTEGER
        LAUNCH_DATA_REAL
        LAUNCH_DATA_BOOL
        LAUNCH_DATA_STRING
        LAUNCH_DATA_OPAQUE
        LAUNCH_DATA_ERRNO
        LAUNCH_DATA_MACHPORT

    launch_data_t launch_data_alloc(launch_data_type_t)
    launch_data_t launch_data_copy(launch_data_t)
    launch_data_type_t launch_data_get_type(const launch_data_t)
    void launch_data_free(launch_data_t)

    bool launch_data_dict_insert(launch_data_t, const launch_data_t, const char *)
    launch_data_t launch_data_dict_lookup(const launch_data_t, const char *)
    bool launch_data_dict_remove(launch_data_t, const char *)
    void launch_data_dict_iterate(const launch_data_t, void (*)(const launch_data_t, const char *, void *), void *)
    size_t launch_data_dict_get_count(const launch_data_t)

    bool launch_data_array_set_index(launch_data_t, const launch_data_t, size_t)
    launch_data_t launch_data_array_get_index(const launch_data_t, size_t)
    size_t launch_data_array_get_count(const launch_data_t)

    launch_data_t launch_data_new_fd(int)
    launch_data_t launch_data_new_machport(mach_port)
    launch_data_t launch_data_new_integer(long long)
    launch_data_t launch_data_new_bool(bool)
    launch_data_t launch_data_new_real(double)
    launch_data_t launch_data_new_string(const char *)
    launch_data_t launch_data_new_opaque(const void *, size)

    bool launch_data_set_fd(launch_data_t, int)
    bool launch_data_set_machport(launch_data_t, mach_port)
    bool launch_data_set_integer(launch_data_t, long long)
    bool launch_data_set_bool(launch_data_t, bool)
    bool launch_data_set_real(launch_data_t, double)
    bool launch_data_set_string(launch_data_t, const char *)
    bool launch_data_set_opaque(launch_data_t, const void *, size)

    int	launch_data_get_fd(const launch_data_t)
    mach_port_t launch_data_get_machport(const launch_data_t)
    long long launch_data_get_integer(const launch_data_t)
    bool launch_data_get_bool(const launch_data_t)
    double launch_data_get_real(const launch_data_t)
    const char* launch_data_get_string(const launch_data_t)
    void* launch_data_get_opaque(const launch_data_t)
    size_t launch_data_get_opaque_size(const launch_data_t)
    int launch_data_get_errno(const launch_data_t)

    int launch_get_fd()
    launch_data_t launch_msg(const launch_data_t) nogil