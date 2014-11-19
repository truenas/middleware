#+
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


import os
import subprocess


def run(context):
    for keytype in ('host', 'rsa', 'dsa', 'ecdsa', 'ed25519'):
        private_key = context.config.get('service.sshd.keys.{0}.private'.format(keytype))
        public_key = context.config.get('service.sshd.keys.{0}.public'.format(keytype))
        private_key_file = '/etc/ssh/ssh_host_{0}_key'.format(keytype)
        public_key_file = private_key_file + '.pub'

        if private_key is None or public_key is None:
            try:
                subprocess.check_call(['/usr/bin/ssh-keygen', '-t', keytype])
            except subprocess.CalledProcessError:
                raise
        else:
            fd = open(private_key_file, 'w')
            fd.write(private_key)
            fd.close()

            fd = open(public_key_file, 'w')
            fd.write(public_key)
            fd.close()

        context.emit_event('etcd.regenerated_file', {
            'filename': private_key_file
        })

        context.emit_event('etcd.regenerated_file', {
            'filename': public_key_file
        })