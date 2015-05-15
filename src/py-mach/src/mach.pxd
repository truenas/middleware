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

cdef extern from "mach/kern_return.h":
    enum:
        KERN_SUCCESS
        KERN_INVALID_ADDRESS
        KERN_PROTECTION_FAILURE
        KERN_NO_SPACE
        KERN_INVALID_ARGUMENT
        KERN_FAILURE
        KERN_RESOURCE_SHORTAGE
        KERN_NOT_RECEIVER
        KERN_NO_ACCESS
        KERN_MEMORY_FAILURE
        KERN_MEMORY_ERROR
        KERN_NOT_IN_SET
        KERN_NAME_EXISTS
        KERN_ABORTED
        KERN_INVALID_NAME
        KERN_INVALID_RIGHT
        KERN_INVALID_VALUE
        KERN_UREFS_OVERFLOW
        KERN_INVALID_CAPABILITY
        KERN_RIGHT_EXISTS
        KERN_INVALID_HOST
        KERN_MEMORY_PRESENT
        KERN_MEMORY_DATA_MOVED
        KERN_MEMORY_RESTART_COPY
        KERN_INVALID_PROCESSOR_SET
        KERN_POLICY_LIMIT
        KERN_INVALID_POLICY
        KERN_INVALID_OBJECT
        KERN_ALREADY_WAITING
        KERN_DEFAULT_SET
        KERN_EXCEPTION_PROTECTED
        KERN_INVALID_LEDGER
        KERN_INVALID_MEMORY_CONTROL
        KERN_INVALID_SECURITY
        KERN_NOT_DEPRESSED
        KERN_TERMINATED
        KERN_LOCK_SET_DESTROYED
        KERN_LOCK_UNSTABLE
        KERN_LOCK_OWNED
        KERN_LOCK_OWNED_SELF
        KERN_SEMAPHORE_DESTROYED
        KERN_RPC_CONTINUE_ORPHAN
        KERN_NOT_SUPPORTED
        KERN_NODE_DOWN
        KERN_NOT_WAITING
        KERN_OPERATION_TIMED_OUT
        KERN_RETURN_MAX


cdef extern from "mach/mach.h" nogil:
    ctypedef int boolean_t
    ctypedef int mach_msg_return_t
    ctypedef int mach_msg_option_t
    ctypedef int mach_msg_size_t
    ctypedef int mach_msg_timeout_t
    ctypedef int mach_msg_bits_t
    ctypedef int mach_port_seqno_t
    ctypedef int mach_msg_id_t
    ctypedef int mach_port_t
    ctypedef int mach_port_name_t
    ctypedef int mach_port_right_t
    ctypedef int mach_msg_trailer_type_t
    ctypedef int mach_msg_trailer_size_t
    ctypedef int kern_return_t
    ctypedef int ipc_space_t
    ctypedef int mach_msg_type_name_t
    ctypedef int mach_msg_copy_options_t
    ctypedef int mach_msg_descriptor_type_t

    ctypedef struct mach_msg_header_t:
        mach_msg_bits_t msgh_bits
        mach_msg_size_t msgh_size
        mach_port_t msgh_remote_port
        mach_port_t msgh_local_port
        mach_port_name_t msgh_voucher_port
        mach_msg_id_t msgh_id

    ctypedef struct mach_msg_trailer_t:
        mach_msg_trailer_type_t msgh_trailer_type
        mach_msg_trailer_size_t msgh_trailer_size

    ctypedef struct mach_msg_type_descriptor_t:
        void* pad1
        mach_msg_size_t pad2
        unsigned int pad3
        mach_msg_descriptor_type_t type

    ctypedef struct mach_msg_port_descriptor_t:
        mach_port_t name
        mach_msg_size_t pad1
        unsigned int pad2
        mach_msg_type_name_t disposition
        mach_msg_descriptor_type_t type

    ctypedef struct mach_msg_ool_descriptor_t:
        void* address
        mach_msg_size_t size
        boolean_t deallocate
        mach_msg_copy_options_t copy
        unsigned int pad1
        mach_msg_descriptor_type_t type

    mach_msg_return_t mach_msg(mach_msg_header_t *msg, mach_msg_option_t option, mach_msg_size_t send_size,
                               mach_msg_size_t rcv_size, mach_port_t rcv_name, mach_msg_timeout_t timeout,
                               mach_port_t notify)

    mach_msg_return_t mach_msg_send(mach_msg_header_t *msg)
    mach_msg_return_t mach_msg_receive(mach_msg_header_t *msg)
    kern_return_t mach_port_allocate(mach_port_t task, mach_port_right_t right, mach_port_t* name)
    kern_return_t mach_port_insert_right(ipc_space_t task, mach_port_name_t name, mach_port_right_t right,
                                         mach_msg_type_name_t right_type)

cdef extern from "mach/port.h" nogil:
    enum:
        MACH_PORT_RIGHT_SEND
        MACH_PORT_RIGHT_RECEIVE
        MACH_PORT_RIGHT_SEND_ONCE
        MACH_PORT_RIGHT_PORT_SET
        MACH_PORT_RIGHT_DEAD_NAME

    enum:
        MACH_PORT_NULL

cdef extern from "mach/message.h" nogil:
    ctypedef int mach_msg_return_t

    enum:
        MACH_MSG_TYPE_MOVE_RECEIVE
        MACH_MSG_TYPE_MOVE_SEND
        MACH_MSG_TYPE_MOVE_SEND_ONCE
        MACH_MSG_TYPE_COPY_SEND
        MACH_MSG_TYPE_MAKE_SEND
        MACH_MSG_TYPE_MAKE_SEND_ONCE

    enum:
        MACH_MSG_PORT_DESCRIPTOR
        MACH_MSG_OOL_DESCRIPTOR
        MACH_MSG_OOL_PORTS_DESCRIPTOR
        MACH_MSG_OOL_VOLATILE_DESCRIPTOR

    enum:
        MACH_MSG_SUCCESS
        MACH_MSG_MASK
        MACH_MSG_IPC_SPACE
        MACH_MSG_VM_SPACE
        MACH_MSG_IPC_KERNEL
        MACH_MSG_VM_KERNEL
        MACH_SEND_IN_PROGRESS
        MACH_SEND_INVALID_DATA
        MACH_SEND_INVALID_DEST
        MACH_SEND_TIMED_OUT
        MACH_SEND_INTERRUPTED
        MACH_SEND_MSG_TOO_SMALL
        MACH_SEND_INVALID_REPLY
        MACH_SEND_INVALID_RIGHT
        MACH_SEND_INVALID_NOTIFY
        MACH_SEND_INVALID_MEMORY
        MACH_SEND_NO_BUFFER
        MACH_SEND_TOO_LARGE
        MACH_SEND_INVALID_TYPE
        MACH_SEND_INVALID_HEADER
        MACH_SEND_INVALID_TRAILER
        MACH_SEND_INVALID_RT_OOL_SIZE
        MACH_RCV_IN_PROGRESS
        MACH_RCV_INVALID_NAME
        MACH_RCV_TIMED_OUT
        MACH_RCV_TOO_LARGE
        MACH_RCV_INTERRUPTED
        MACH_RCV_PORT_CHANGED
        MACH_RCV_INVALID_NOTIFY
        MACH_RCV_INVALID_DATA
        MACH_RCV_PORT_DIED
        MACH_RCV_IN_SET
        MACH_RCV_HEADER_ERROR
        MACH_RCV_BODY_ERROR
        MACH_RCV_INVALID_TYPE
        MACH_RCV_SCATTER_SMALL
        MACH_RCV_INVALID_TRAILER
        MACH_RCV_IN_PROGRESS_TIMED

    enum:
        MACH_MSG_TIMEOUT_NONE
        MACH_SEND_MSG
        MACH_RCV_MSG


cdef extern from "mach/mach_init.h" nogil:
    mach_port_t mach_task_self()

cdef extern from "servers/bootstrap.h" nogil:
    enum:
        BOOTSTRAP_MAX_NAME_LEN

    ctypedef char[BOOTSTRAP_MAX_NAME_LEN] name_t

    mach_port_t bootstrap_port
    kern_return_t bootstrap_create_service(mach_port_t bp, const name_t service_name, mach_port_t *sp)
    kern_return_t bootstrap_check_in(mach_port_t bp, const name_t service_name, mach_port_t *sp)
    kern_return_t bootstrap_look_up(mach_port_t bp, const name_t service_name, mach_port_t *sp)