#!/usr/local/bin/python
#
# Copyright iXsystems, Inc. 2011

import os
import tempfile

import pexpect

cert = 'server.crt'
key = 'server.key'

csr = tempfile.mktemp()

for f in (cert, key, ):
    try:
        os.unlink(f)
    except:
        pass

p = pexpect.spawn('openssl genrsa -des3 -out %s 2048' % (key, ))
try:
    p.expect('Generating.* ', timeout=2)
    p.expect('Enter pass.*:', timeout=5)
    p.sendline('freebsd')
    p.expect('Verifying - Enter pass.*:', timeout=5)
    p.sendline('freebsd')
finally:
    p.close()

csr = tempfile.mktemp()
p = pexpect.spawn('openssl req -new -key %s -out %s'
                  % (key, csr, ))
try:
    p.expect('Enter pass.*:', timeout=5)
    p.sendline('freebsd')
    p.expect('Country.*:', 10)
    p.sendline('US')
    p.expect('State.*:', 10)
    p.sendline('CA')
    p.expect('Locality.*:', 10)
    p.sendline('Berkeley')
    p.expect('Organization Name.*:', 10)
    p.sendline('FreeBSD')
    p.expect('Organizational Unit Name.*:', 10)
    p.sendline('Foundation')
    p.expect('Common Name.*:', 10)
    p.sendline('Beastie')
    p.expect('Email Address.*:', 10)
    p.sendline('beastie@freebsd.local')
    p.expect('A challenge.*:', 10)
    p.sendline('A challenge you say?')
    p.expect('An optional company name.*:', 10)
    p.sendline('UCB')
finally:
    p.close()

try:
    os.system('cp %(key)s %(key)s.org' % { 'key': key, })
    p = pexpect.spawn('openssl rsa -in %(key)s.org -out %(key)s'
                      % { 'key': key, })
    try:
        p.expect('Enter pass.*:', timeout=5)
        p.sendline('freebsd')
        p.expect(pexpect.EOF, 10)
    finally:
        p.close()

    p = pexpect.spawn('openssl x509 -req -days 10 -in %s -signkey %s -out %s'
                      % (csr, key, cert, ))
    try:
        p.expect('Getting Private key', 10)
        p.expect(pexpect.EOF, 10)
    finally:
        p.close()
finally:
    try:
        os.unlink(csr)
    except:
        pass
