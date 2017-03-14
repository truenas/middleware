#!/usr/local/bin/python
# Copyright (c) 2012, Jakob Borg
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * The name of the author may not be used to endorse or promote products
#      derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY JAKOB BORG ''AS IS'' AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
# EVENT SHALL JAKOB BORG BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT
# OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.
# Initial code taken from: https://github.com/jm66/solaris-extra-snmp


def decompose_oid(oid):
    return [int(o) for o in oid.split('.')[1:]]


def oid_compare(a, b):
    ad = decompose_oid(a)
    bd = decompose_oid(b)
    return cmp(ad, bd)


def printValue(value, oid):
    # If it's a function, call it.
    if type(value).__name__ == 'function':
        value = value(oid)
    # Otherwise assume it's a two-tuple of type and value.
    print(value[0])
    print(value[1])


def respond_to(operation, req_oid, result):
    result = sorted(result, key=lambda row: decompose_oid(row[0]))

    if operation == '-g':
        for oid, value in result:
            if oid == req_oid:
                print(oid)
                printValue(value, oid)
    elif operation == '-n':
        for oid, value in result:
            if oid_compare(oid, req_oid) == 1:
                print(oid)
                printValue(value, oid)
                break
