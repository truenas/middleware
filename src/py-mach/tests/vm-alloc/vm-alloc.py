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

import mach
from utils import fail


BUFSIZE = 1024


def main():
    buf = mach.MemoryBuffer()
    assert not buf.allocated
    assert buf.size == 0
    assert buf.address == 0

    buf.allocate(BUFSIZE)
    assert buf.allocated
    assert buf.size == BUFSIZE
    assert buf.address != 0

    print 'Buffer address: 0x{0:x}'.format(buf.address)

    buf.deallocate()
    assert not buf.allocated
    assert buf.size == 0
    assert buf.address == 0

    buf = mach.MemoryBuffer(data=bytearray('Testing 1234'))
    assert buf.allocated
    assert buf.size == len(bytearray('Testing 1234'))
    buf[0] = ord('F')
    assert buf.data == bytearray('Festing 1234')
    buf.deallocate()
    assert not buf.allocated

if __name__ == '__main__':
    main()