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
	
	#
	#	If NFS is disabled, exit.
	#

	local nfs_enabled

	nfs_enabled=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		srv_enable
	FROM
		service_services
	WHERE
		srv_service = 'nfs'
	")
	
	section_header "NFS Status"	
	if [ "${nfs_enabled}" = "0" ]
	then
		echo "NFS is DISABLED"
		exit 0
	fi

	section_header "/etc/hosts"
	sc "/etc/hosts"
	section_footer

	section_header "/etc/exports"
	sc /etc/exports
	section_footer

	section_header "showmount -e"
	showmount -e
	section_footer

	section_header "rpcinfo -p"
	rpcinfo -p
	section_footer

	section_header "nfsstat"
	nfsstat
	section_footer

	section_header "nfsstat -c"
	nfsstat -c
	section_footer

	section_header "nfsstat -s"
	nfsstat -s
	section_footer

	section_header "nfsv4 locks: nfsdumpstate"
	nfsdumpstate
	section_footer
}
