#!/bin/sh
#+
# Copyright 2018 iXsystems, Inc.
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


doms_opt() { echo M; }
doms_help() { echo "Dump SATA DOMs Information"; }
doms_directory() { echo "DOMS"; }
doms_func()
{
    section_header "SATA DOMS"
    PRODUCT=$( dmidecode -s system-product-name )
    if echo ${PRODUCT} | grep -qe 'TRUENAS.*Z' -qe 'TRUENAS.*M'
    then
        for i in /dev/ada0 /dev/ada1
        do
           if [ -c ${i} ]
           then
               echo ${i}
               smartctl -a ${i} | grep 'Device Model'
               SPEED=$(dd if=${i} of=/dev/null bs=64k count=500 2>&1 | tail -1 | sed 's/^.*secs..//' | sed 's/bytes.*//')
               MBS=$( printf "%10.3f" $( echo ${SPEED} / 1048576  | bc -l ) )
               IMBS=$( echo ${MBS} | sed 's/\..*//' )
               echo ${MBS} MB per second
               if [ ${IMBS} -lt 3 ]; then
                  echo WARNING: ${i} is slow and might be a candidate for SATA DOM replacement.
               fi
            fi
        done
    else
        echo ${PRODUCT} does not use SATA DOMS.  Exiting.
    fi
    section_footer
}
