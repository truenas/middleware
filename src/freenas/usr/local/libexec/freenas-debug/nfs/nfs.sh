#!/bin/sh
#+
# Copyright 2013 iXsystems, Inc.
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


nfs_opt() { echo N; }
nfs_help() { echo "Dump NFS Configuration"; }
nfs_directory() { echo "NFS"; }
nfs_func()
{

	local onoff

        onoff=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
        SELECT
                srv_enable
        FROM
                services_services
        WHERE
                srv_service = 'nfs'
        ORDER BY
                -id
        LIMIT 1
        ")

        enabled="not start on boot."
        if [ "${onoff}" = "1" ]
        then
                enabled="start on boot."
        fi

        section_header "NFS Boot Status"
        echo "NFS will ${enabled}"
        section_footer

	section_header "NFS Service Status"
	systemctl status nfs-ganesha
	section_footer

	section_header "rpcinfo -p"
	rpcinfo -p
	section_footer

	section_header "NFS Config (/etc/ganesha/ganesha.conf)"
	sc "/etc/ganesha/ganesha.conf"
	section_footer

	section_header "NFS Service Configuration"
	midclt call nfs.config | jq
	section_footer

	sectio_header "NFS Shares Configuration"
	midclt call sharing.nfs.query | jq
	section_footer
}
