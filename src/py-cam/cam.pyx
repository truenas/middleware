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


cimport defs
from libc.stdlib cimport free


cdef class CamDevice(object):
    cdef defs.cam_device* dev

    def __init__(self, path):
        self.dev = defs.cam_open_device(path, defs.O_RDWR)
        if self.dev == NULL:
            raise RuntimeError('Cannot open device')

    def __dealloc__(self):
        if self.dev != NULL:
            defs.cam_close_device(self.dev)

    def __getstate__(self):
        return {
            'controller-name': self.controller_name,
            'controller-unit': self.controller_unit,
            'bus-id': self.bus_id,
            'target-id': self.target_id,
            'target-lun': self.target_lun,
            'path-id': self.path_id,
            'serial': self.serial
        }

    property bus_id:
        def __get__(self):
            return self.dev.bus_id

    property controller_name:
        def __get__(self):
            return self.dev.sim_name

    property controller_unit:
        def __get__(self):
            return self.dev.sim_unit_number

    property target_lun:
        def __get__(self):
            return self.dev.target_lun

    property target_id:
        def __get__(self):
            return self.dev.target_id

    property path_id:
        def __get__(self):
            return self.dev.path_id

    property serial:
        def __get__(self):
            return self.dev.serial_num[:self.dev.serial_num_len]
