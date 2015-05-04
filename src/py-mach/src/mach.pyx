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
import cython
cimport mach
from libc.stdint cimport uintptr_t
from libc.stdlib cimport malloc, realloc, free


class KernReturn(enum.IntEnum):
    KERN_SUCCESS = mach.KERN_SUCCESS
    KERN_INVALID_ADDRESS = mach.KERN_INVALID_ADDRESS
    KERN_PROTECTION_FAILURE = mach.KERN_PROTECTION_FAILURE
    KERN_NO_SPACE = mach.KERN_NO_SPACE
    KERN_INVALID_ARGUMENT = mach.KERN_INVALID_ARGUMENT
    KERN_FAILURE = mach.KERN_FAILURE
    KERN_RESOURCE_SHORTAGE = mach.KERN_RESOURCE_SHORTAGE
    KERN_NOT_RECEIVER = mach.KERN_NOT_RECEIVER
    KERN_NO_ACCESS = mach.KERN_NO_ACCESS
    KERN_MEMORY_FAILURE = mach.KERN_MEMORY_FAILURE
    KERN_MEMORY_ERROR = mach.KERN_MEMORY_ERROR
    KERN_ALREADY_IN_SET = mach.KERN_ALREADY_IN_SET
    KERN_NOT_IN_SET = mach.KERN_NOT_IN_SET
    KERN_NAME_EXISTS = mach.KERN_NAME_EXISTS
    KERN_ABORTED = mach.KERN_ABORTED
    KERN_INVALID_NAME = mach.KERN_INVALID_NAME
    KERN_INVALID_RIGHT = mach.KERN_INVALID_RIGHT
    KERN_INVALID_VALUE = mach.KERN_INVALID_VALUE
    KERN_UREFS_OVERFLOW = mach.KERN_UREFS_OVERFLOW
    KERN_INVALID_CAPABILITY = mach.KERN_INVALID_CAPABILITY
    KERN_RIGHT_EXISTS = mach.KERN_RIGHT_EXISTS
    KERN_INVALID_HOST = mach.KERN_INVALID_HOST
    KERN_MEMORY_PRESENT = mach.KERN_MEMORY_PRESENT
    KERN_MEMORY_DATA_MOVED = mach.KERN_MEMORY_DATA_MOVED
    KERN_MEMORY_RESTART_COPY = mach.KERN_MEMORY_RESTART_COPY
    KERN_INVALID_PROCESSOR_SET = mach.KERN_INVALID_PROCESSOR_SET
    KERN_POLICY_LIMIT = mach.KERN_POLICY_LIMIT
    KERN_INVALID_POLICY = mach.KERN_INVALID_POLICY
    KERN_INVALID_OBJECT = mach.KERN_INVALID_OBJECT
    KERN_ALREADY_WAITING = mach.KERN_ALREADY_WAITING
    KERN_DEFAULT_SET = mach.KERN_DEFAULT_SET
    KERN_EXCEPTION_PROTECTED = mach.KERN_EXCEPTION_PROTECTED
    KERN_INVALID_LEDGER = mach.KERN_INVALID_LEDGER
    KERN_INVALID_MEMORY_CONTROL = mach.KERN_INVALID_MEMORY_CONTROL
    KERN_INVALID_SECURITY = mach.KERN_INVALID_SECURITY
    KERN_NOT_DEPRESSED = mach.KERN_NOT_DEPRESSED
    KERN_TERMINATED = mach.KERN_TERMINATED
    KERN_LOCK_SET_DESTROYED = mach.KERN_LOCK_SET_DESTROYED
    KERN_LOCK_UNSTABLE = mach.KERN_LOCK_UNSTABLE
    KERN_LOCK_OWNED = mach.KERN_LOCK_OWNED
    KERN_LOCK_OWNED_SELF = mach.KERN_LOCK_OWNED_SELF
    KERN_SEMAPHORE_DESTROYED = mach.KERN_SEMAPHORE_DESTROYED
    KERN_RPC_SERVER_TERMINATE = mach.KERN_RPC_SERVER_TERMINATE
    KERN_RPC_CONTINUE_ORPHAN = mach.KERN_RPC_CONTINUE_ORPHAN
    KERN_NOT_SUPPORTED = mach.KERN_NOT_SUPPORTED
    KERN_NODE_DOWN = mach.KERN_NODE_DOWN
    KERN_NOT_WAITING = mach.KERN_NOT_WAITING
    KERN_OPERATION_TIMED_OUT = mach.KERN_OPERATION_TIMED_OUT
    KERN_CODESIGN_ERROR = mach.KERN_CODESIGN_ERROR
    KERN_POLICY_STATIC = mach.KERN_POLICY_STATIC
    KERN_RETURN_MAX = mach.KERN_RETURN_MAX


class MachException(Exception):
    pass


cdef class Port:
    def __init__(self):
        pass

    cdef send(self, dest_port, Message message):
        cdef mach.mach_msg_header_t* msg
        cdef mach.kern_return_t kr

        msg = <mach.mach_msg_header_t*><void*>message.ptr()
        kr = mach.mach_msg_send(msg)
        if kr != mach.KERN_SUCCESS:
            raise MachException(kr)

    cdef receive(self, max_size=16384):
        cdef mach.mach_msg_header_t* ptr
        cdef mach.kern_return_t kr

        msg = Message(size=max_size)
        ptr = <mach.mach_msg_header_t*><void*>msg.ptr()
        kr = mach.mach_msg_receive(ptr)
        if kr != mach.KERN_SUCCESS:
            raise MachException(kr)


cdef class Message:
    cdef mach.mach_msg_header_t *msg
    cdef int length

    def __init__(self, size=None):
        self.msg = <mach.mach_msg_header_t*>malloc(cython.sizeof(mach.mach_msg_header_t))
        if size:
            self.size = size

    cdef uintptr_t ptr(self):
        return <uintptr_t>self.msg

    def resize(self, body_size):
        self.length = body_size + cython.sizeof(mach.mach_msg_header_t)
        self.msg = <mach.mach_msg_header_t*>realloc(<void*>self.msg, self.length)
        self.msg.msgh_size = self.length

    property body:
        def __get__(self):
            cdef char* body

            body = <char*>self.msg + cython.sizeof(mach.mach_msg_header_t)
            return body[:self.size]

        def __set__(self, value):
            self.size = len(value)
            self.body = value

    property size:
        def __get__(self):
            return self.msg.msgh_size

        def __set__(self, value):
            self.resize(value)

    property id:
        def __get__(self):
            return self.msg.msgh_id

        def __set__(self, value):
            self.msg.msgh_id = value


    property remote_port:
        def __get__(self):
            return self.msg.msgh_remote_port

        def __set__(self, value):
            self.msg.msgh_remote_port = value

    property local_port:
        def __get__(self):
            return self.msg.msgh_local_port

        def __set__(self, value):
            self.msg.msgh_local_port = value

    property bits:
        def __get__(self):
            pass


cdef class BootstrapServer:
    def __init__(self):
        pass


def create_service(name):
    cdef mach.kern_return_t kr
    cdef mach.mach_port_t port

    kr = mach.bootstrap_create_service(mach.bootstrap_port, name, &port)
    if kr != mach.KERN_SUCCESS:
        raise MachException(kr)

    kr = mach.bootstrap_check_in(mach.bootstrap_port, name, &port)
    if kr != mach.KERN_SUCCESS:
        raise MachException(kr)

    return Port(port)