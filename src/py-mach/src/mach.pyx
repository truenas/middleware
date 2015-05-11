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
from libc.string cimport memmove, memset


class PortRight(enum.IntEnum):
    MACH_PORT_RIGHT_SEND = mach.MACH_PORT_RIGHT_SEND
    MACH_PORT_RIGHT_RECEIVE = mach.MACH_PORT_RIGHT_RECEIVE
    MACH_PORT_RIGHT_SEND_ONCE = mach.MACH_PORT_RIGHT_SEND_ONCE
    MACH_PORT_RIGHT_PORT_SET = mach.MACH_PORT_RIGHT_PORT_SET
    MACH_PORT_RIGHT_DEAD_NAME = mach.MACH_PORT_RIGHT_DEAD_NAME


class MessageType(enum.IntEnum):
    MACH_MSG_TYPE_MOVE_RECEIVE = mach.MACH_MSG_TYPE_MOVE_RECEIVE
    MACH_MSG_TYPE_MOVE_SEND = mach.MACH_MSG_TYPE_MOVE_SEND
    MACH_MSG_TYPE_MOVE_SEND_ONCE = mach.MACH_MSG_TYPE_MOVE_SEND_ONCE
    MACH_MSG_TYPE_COPY_SEND = mach.MACH_MSG_TYPE_COPY_SEND
    MACH_MSG_TYPE_MAKE_SEND = mach.MACH_MSG_TYPE_MAKE_SEND
    MACH_MSG_TYPE_MAKE_SEND_ONCE = mach.MACH_MSG_TYPE_MAKE_SEND_ONCE


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
    KERN_RPC_CONTINUE_ORPHAN = mach.KERN_RPC_CONTINUE_ORPHAN
    KERN_NOT_SUPPORTED = mach.KERN_NOT_SUPPORTED
    KERN_NODE_DOWN = mach.KERN_NODE_DOWN
    KERN_NOT_WAITING = mach.KERN_NOT_WAITING
    KERN_OPERATION_TIMED_OUT = mach.KERN_OPERATION_TIMED_OUT
    KERN_RETURN_MAX = mach.KERN_RETURN_MAX


class MessageSendReturn(enum.IntEnum):
    MACH_MSG_SUCCESS = mach.MACH_MSG_SUCCESS
    MACH_MSG_MASK = mach.MACH_MSG_MASK
    MACH_MSG_IPC_SPACE = mach.MACH_MSG_IPC_SPACE
    MACH_MSG_VM_SPACE = mach.MACH_MSG_VM_SPACE
    MACH_MSG_IPC_KERNEL = mach.MACH_MSG_IPC_KERNEL
    MACH_MSG_VM_KERNEL = mach.MACH_MSG_VM_KERNEL
    MACH_SEND_IN_PROGRESS = mach.MACH_SEND_IN_PROGRESS
    MACH_SEND_INVALID_DATA = mach.MACH_SEND_INVALID_DATA
    MACH_SEND_INVALID_DEST = mach.MACH_SEND_INVALID_DEST
    MACH_SEND_TIMED_OUT = mach.MACH_SEND_TIMED_OUT
    MACH_SEND_INTERRUPTED = mach.MACH_SEND_INTERRUPTED
    MACH_SEND_MSG_TOO_SMALL = mach.MACH_SEND_MSG_TOO_SMALL
    MACH_SEND_INVALID_REPLY = mach.MACH_SEND_INVALID_REPLY
    MACH_SEND_INVALID_RIGHT = mach.MACH_SEND_INVALID_RIGHT
    MACH_SEND_INVALID_NOTIFY = mach.MACH_SEND_INVALID_NOTIFY
    MACH_SEND_INVALID_MEMORY = mach.MACH_SEND_INVALID_MEMORY
    MACH_SEND_NO_BUFFER = mach.MACH_SEND_NO_BUFFER
    MACH_SEND_TOO_LARGE = mach.MACH_SEND_TOO_LARGE
    MACH_SEND_INVALID_TYPE = mach.MACH_SEND_INVALID_TYPE
    MACH_SEND_INVALID_HEADER = mach.MACH_SEND_INVALID_HEADER
    MACH_SEND_INVALID_TRAILER = mach.MACH_SEND_INVALID_TRAILER
    MACH_SEND_INVALID_RT_OOL_SIZE = mach.MACH_SEND_INVALID_RT_OOL_SIZE

class MessageReceiveReturn(enum.IntEnum):
    MACH_RCV_IN_PROGRESS = mach.MACH_RCV_IN_PROGRESS
    MACH_RCV_INVALID_NAME = mach.MACH_RCV_INVALID_NAME
    MACH_RCV_TIMED_OUT = mach.MACH_RCV_TIMED_OUT
    MACH_RCV_TOO_LARGE = mach.MACH_RCV_TOO_LARGE
    MACH_RCV_INTERRUPTED = mach.MACH_RCV_INTERRUPTED
    MACH_RCV_PORT_CHANGED = mach.MACH_RCV_PORT_CHANGED
    MACH_RCV_INVALID_NOTIFY = mach.MACH_RCV_INVALID_NOTIFY
    MACH_RCV_INVALID_DATA = mach.MACH_RCV_INVALID_DATA
    MACH_RCV_PORT_DIED = mach.MACH_RCV_PORT_DIED
    MACH_RCV_IN_SET = mach.MACH_RCV_IN_SET
    MACH_RCV_HEADER_ERROR = mach.MACH_RCV_HEADER_ERROR
    MACH_RCV_BODY_ERROR = mach.MACH_RCV_BODY_ERROR
    MACH_RCV_INVALID_TYPE = mach.MACH_RCV_INVALID_TYPE
    MACH_RCV_SCATTER_SMALL = mach.MACH_RCV_SCATTER_SMALL
    MACH_RCV_INVALID_TRAILER = mach.MACH_RCV_INVALID_TRAILER
    MACH_RCV_IN_PROGRESS_TIMED = mach.MACH_RCV_IN_PROGRESS_TIMED


class MachException(Exception):
    pass


class MessageSendException(Exception):
    def __init__(self, no):
        self.code = MessageSendReturn(no)

    def __str__(self):
        return self.code.name


class MessageReceiveException(Exception):
    def __init__(self, no):
        self.code = MessageReceiveReturn(no)

    def __str__(self):
        return self.code.name


cdef class Port:
    cdef mach_port_t port

    def __init__(self, port=None, right=PortRight.MACH_PORT_RIGHT_RECEIVE):
        if port is not None:
            self.port = port
        else:
            self.port = self.allocate_port(right)

    def __str__(self):
        return '<Mach port {0}>'.format(self.port)

    cdef mach_port_t value(self):
        return self.port

    def insert_right(self, right):
        cdef mach.mach_msg_return_t kr
        cdef mach.mach_msg_type_name_t type = right.value

        with nogil:
            kr = mach.mach_port_insert_right(mach_task_self(), self.port, self.port, type)
        if kr != mach.KERN_SUCCESS:
            raise MachException(kr)

    def allocate_port(self, right):
        cdef mach.mach_port_t port
        cdef mach.kern_return_t kr

        kr = mach.mach_port_allocate(mach_task_self(), right.value, &port)
        if kr != mach.KERN_SUCCESS:
            raise MachException(kr)

        return port

    def send(self, Port dest, Message message):
        cdef mach.mach_msg_header_t* msg
        cdef mach.mach_msg_return_t kr

        msg = <mach.mach_msg_header_t*><void*>message.ptr()
        msg.msgh_local_port = self.port
        msg.msgh_remote_port = dest.value()
        with nogil:
            kr = mach.mach_msg_send(msg)
        if kr != mach.KERN_SUCCESS:
            raise MessageSendException(kr)

    def send_overwrite(self, Port dest, Message message):
        cdef mach.mach_msg_header_t* msg
        cdef mach.mach_msg_return_t kr

        msg = <mach.mach_msg_header_t*><void*>message.ptr()
        msg.msgh_local_port = self.port
        msg.msgh_remote_port = dest.value()
        with nogil:
            kr = mach.mach_msg(
                msg,
                mach.MACH_SEND_MSG | mach.MACH_RCV_MSG,
                msg.msgh_size,
                msg.msgh_size,
                msg.msgh_local_port,
                mach.MACH_MSG_TIMEOUT_NONE,
                mach.MACH_PORT_NULL)

        if kr != mach.KERN_SUCCESS:
            raise MessageSendException(kr)

        return message

    def receive(self, max_size=16384):
        cdef mach.mach_msg_header_t* ptr
        cdef mach.mach_msg_return_t kr

        msg = Message(size=max_size)
        ptr = <mach.mach_msg_header_t*><void*>msg.ptr()
        ptr.msgh_local_port = self.port
        with nogil:
            kr = mach.mach_msg_receive(ptr)
        if kr != mach.KERN_SUCCESS:
            raise MessageReceiveException(kr)

        return msg


cdef class Message:
    cdef mach.mach_msg_header_t *msg
    cdef char *buffer
    cdef int length

    def __init__(self, size=None):
        self.msg = <mach.mach_msg_header_t*>malloc(cython.sizeof(mach.mach_msg_header_t))
        self.buffer = (<char*>self.msg) + cython.sizeof(mach.mach_msg_header_t)
        if size:
            self.size = size

    cdef uintptr_t ptr(self):
        return <uintptr_t>self.msg

    def resize(self, body_size):
        self.length = body_size + cython.sizeof(mach.mach_msg_header_t)
        self.msg = <mach.mach_msg_header_t*>realloc(<void*>self.msg, self.length)
        self.buffer = (<char*>self.msg) + cython.sizeof(mach.mach_msg_header_t)
        self.msg.msgh_size = self.length

    property body:
        def __get__(self):
            return self.buffer[:self.size - cython.sizeof(mach.mach_msg_header_t)]

        def __set__(self, unsigned char [:] value):
            cdef unsigned char *ptr
            self.size = value.shape[0]
            ptr = &value[0]
            memmove(self.buffer, ptr, value.shape[0])

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
            return Port(self.msg.msgh_remote_port)

        def __set__(self, Port value):
            self.msg.msgh_remote_port = value.value()

    property local_port:
        def __get__(self):
            return Port(self.msg.msgh_local_port)

        def __set__(self, Port value):
            self.msg.msgh_local_port = value.value()

    property bits:
        def __get__(self):
            pass

        def __set__(self, value):
            self.msg.msgh_bits = value


cdef class BootstrapServer:
    def __init__(self):
        pass

    @staticmethod
    def checkin(name):
        cdef mach.kern_return_t kr
        cdef mach.mach_port_t port
        cdef char* n = name

        with nogil:
            kr = mach.bootstrap_check_in(mach.bootstrap_port, n, &port)

        if kr != mach.KERN_SUCCESS:
            raise MachException(kr)

        return Port(port)

    @staticmethod
    def lookup(name):
        cdef mach.kern_return_t kr
        cdef mach.mach_port_t port
        cdef char* n = name

        with nogil:
            kr = mach.bootstrap_look_up(mach.bootstrap_port, n, &port)

        if kr != mach.KERN_SUCCESS:
            raise MachException(kr)

        return Port(port)

def make_msg_bits(remote, local):
    return remote | (local << 8)

null_port = Port(port=mach.MACH_PORT_NULL)