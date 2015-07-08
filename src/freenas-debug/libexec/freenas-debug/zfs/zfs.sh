#!/bin/sh
#+
# Copyright 2011 iXsystems, Inc.
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


zfs_opt() { echo z; }
zfs_help() { echo "Dump ZFS configuration"; }
zfs_directory() { echo "ZFS"; }
zfs_func()
{
	section_header "ZFS Pools"
	zpool list
	section_footer

	section_header "ZFS Pools Status"
	zpool status
	section_footer

	section_header "ZFS Pools History"
	zpool history
	section_footer

	section_header "ZFS Pools Properties"
	pools=$(zpool list -H|awk '{ print $1 }'|xargs)
	for p in ${pools}
	do
		section_header "${p}"
		zpool get all ${p}
		section_footer
	done
	section_footer

	section_header "ZFS Datasets and ZVols"
	zfs list
	section_footer

	section_header "ZFS Snapshots"
	zfs list -t snapshot -o name,used,available,referenced,mountpoint,freenas:state
	section_footer

	section_header "ZFS Datasets Properties"
	sets=$(zfs list -H|awk '{ print $1 }'|xargs)
	for s in ${sets}
	do
		section_header "${s}"
		zfs get all ${s}
		section_footer
	done
	section_footer
}
