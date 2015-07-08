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
	section_header "/etc/version"
	sc "/etc/version"
	section_footer

	section_header "/etc/resolv.conf"
	sc "/etc/resolv.conf"
	section_footer

	section_header "/etc/hosts"
	sc "/etc/hosts"
	section_footer

	section_header "/etc/exports"
	sc /etc/exports
	section_footer
	
	section_header "showmount -e"
	if srv_enabled nfs
	then
		showmount -e
	fi
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

	section_header "netstat -m"
	netstat -m
	section_footer

	section_header "netstat -s -p udp"
	netstat -s -p udp
	section_footer

	section_header "getent passwd"
	getent passwd
	section_footer

	section_header "getent group"
	getent group
	section_footer
}
