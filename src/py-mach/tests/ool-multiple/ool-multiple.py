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

import struct
import threading
import random
import string
import mach
from utils import fail


descriptors = []


def random_str(len):
    set = string.letters + string.digits + string.punctuation
    return ''.join([random.choice(set) for _ in range(len)])


def describe_msg(msg):
    print 'Body length: {0}'.format(len(msg.body))
    print 'Descriptors:'
    for idx, desc in enumerate(msg.descriptors):
        print 'Descriptor #{0}: {1}'.format(idx, str(desc))
        print '    address: 0x{0:x}, size: {1}'.format(desc.address, desc.size)

def server(port):
    try:
        msg = port.receive()
    except mach.MessageReceiveException, e:
        fail('Cannot receive message: {0}'.format(e))

    print 'Received message:'
    describe_msg(msg)
    contents, = struct.unpack('256p', msg.body)

    if len(msg.body) != 256:
        fail('Invalid body length, {0} instead of {1}'.format(msg.body, 256))

    print 'Received text: {0}'.format(contents)

    if contents != 'Hello World':
        fail('Invalid message payload returned: {0}'.format(contents))

    for i in range(0, len(descriptors)):
        if msg.descriptors[i].size != descriptors[i].size:
            fail('Descriptor #{0}: invalid size ({1} != {2})'.format(i, msg.descriptors[i].size, descriptors[i].size))

        if msg.descriptors[i].buffer.data != descriptors[i].buffer.data:
            fail('Descriptor #{0}: data mismatch')

        print 'Descriptor #{0}: OK'.format(i)


def main():
    # Create send port
    try:
        send = mach.Port()
        send.insert_right(mach.MessageType.MACH_MSG_TYPE_MAKE_SEND)
        print 'Send port: {0}'.format(send)
    except mach.MachException, e:
        fail('Cannot create send port: {0}'.format(e))

    # Create receive port
    try:
        receive = mach.Port()
        receive.insert_right(mach.MessageType.MACH_MSG_TYPE_MAKE_SEND)
        print 'Receive port: {0}'.format(receive)
    except mach.MachException, e:
        fail('Cannot create receive port: {0}'.format(e))

    # Prepare descriptors
    for i in range(0, random.randrange(5, 15)):
        buffer = mach.MemoryBuffer(data=bytearray(random_str(random.randrange(1, 1024 * 1024))))
        desc = mach.MemoryDescriptor()
        desc.buffer = buffer
        descriptors.append(desc)

    t = threading.Thread(target=server, args=(receive,))
    t.start()

    msg = mach.Message()
    msg.bits = mach.make_msg_bits(mach.MessageType.MACH_MSG_TYPE_COPY_SEND, mach.MessageType.MACH_MSG_TYPE_MAKE_SEND)
    msg.descriptors = descriptors
    msg.body = bytearray(struct.pack('256p', 'Hello World'))

    print 'Text to send: {0}'.format('Hello World')
    print 'Message to send:'
    describe_msg(msg)

    try:
        send.send(receive, msg)
    except mach.MessageSendException, e:
        fail('Cannot send message: {0}'.format(e))


if __name__ == '__main__':
    main()