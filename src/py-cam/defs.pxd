#-
# Copyright (c) 2015 iXsystems, Inc.
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

from libc.stdint cimport *


cdef extern from "fcntl.h":
    enum:
        O_RDWR


cdef extern from "camlib.h":
    ctypedef int path_id_t
    ctypedef int lun_id_t
    ctypedef int target_id_t

    enum:
        MAXPATHLEN
        DEV_IDLEN
        SIM_IDLEN

    cdef struct cam_device:
        char device_path[MAXPATHLEN + 1]
        char given_dev_name[DEV_IDLEN + 1]
        uint32_t given_unit_number
        char device_name[DEV_IDLEN + 1]
        uint32_t dev_unit_num
        char sim_name[SIM_IDLEN + 1]
        uint32_t sim_unit_number
        uint32_t bus_id
        lun_id_t target_lun
        target_id_t target_id
        path_id_t path_id
        uint16_t pd_type
        uint8_t serial_num[252]
        uint8_t serial_num_len
        uint8_t sync_period
        uint8_t sync_offset
        uint8_t bus_width
        int fd

    cdef cam_device* cam_open_device(char* path, int flags)
