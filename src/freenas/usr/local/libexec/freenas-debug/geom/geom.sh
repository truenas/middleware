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


geom_opt() { echo g; }
geom_help() { echo "Dump GEOM Configuration"; }
geom_directory() { echo "Geom"; }
geom_func()
{
	geom_inode=$(ls -i /sbin/geom|awk '{ print $1 }')
	classes=$(ls -i /sbin|grep "^${geom_inode}"|awk '{ print $2 }')

	section_header "GEOM disks (geom disk list)"
	geom disk list
	section_footer

	section_header "GEOM classes"
	for c in ${classes}
	do
		if $(${c} status >/dev/null 2>&1)
		then
			list=$(${c} list)
			status=$(${c} status)
			if [ -z "${list}" -a -z "${status}" ]
			then
				continue
			fi

			if [ -n "${list}" ]
			then
				section_header "${c} list"
				${c} list
				section_footer
			fi

			if [ -n "${status}" ]
			then
				section_header "${c} status"
				${c} status
				section_footer
			fi
		fi
	done
	section_footer

	section_header "GEOM labels - 'glabel status'"
	glabel status
	section_footer
}
