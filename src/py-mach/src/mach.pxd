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
        KERN_ALREADY_IN_SET
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
        KERN_RPC_SERVER_TERMINATE
        KERN_RPC_CONTINUE_ORPHAN
        KERN_NOT_SUPPORTED
        KERN_NODE_DOWN
        KERN_NOT_WAITING
        KERN_OPERATION_TIMED_OUT
        KERN_CODESIGN_ERROR
        KERN_POLICY_STATIC
        KERN_RETURN_MAX


cdef extern from "mach/mach.h":
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
    ctypedef int kern_return_t

    ctypedef struct mach_msg_header_t:
        mach_msg_bits_t msgh_bits
        mach_msg_size_t msgh_size
        mach_port_t msgh_remote_port
        mach_port_t msgh_local_port
        mach_port_name_t msgh_voucher_port
        mach_msg_id_t msgh_id

    ctypedef struct mach_msg_trailer_t:
        pass

    mach_msg_return_t mach_msg(mach_msg_header_t *msg,
                               mach_msg_option_t option,
                               mach_msg_size_t send_size,
                               mach_msg_size_t rcv_size,
                               mach_msg_timeout_t timeout,
                               mach_port_t notify)

    mach_msg_return_t mach_msg_send(mach_msg_header_t *msg)
    mach_msg_return_t mach_msg_receive(mach_msg_header_t *msg)
    kern_return_t mach_port_allocate(mach_port_t task, mach_port_right_t right, mach_port_t* name)

cdef extern from "mach/mach_init.h":
    mach_port_t mach_task_self()

cdef extern from "servers/bootstrap.h":
    ctypedef char[1] name_t

    mach_port_t bootstrap_port
    kern_return_t bootstrap_create_service(mach_port_t bp, const name_t service_name, mach_port_t *sp)
    kern_return_t bootstrap_check_in(mach_port_t bp, const name_t service_name, mach_port_t *sp)