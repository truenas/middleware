#!/bin/sh
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


smart_opt() { echo S; }
smart_help() { echo "Dump SMART Information"; }
smart_directory() { echo "SMART"; }
smart_func()
{

	local smart_onoff=0
	local smart_enabled="not start on boot."

	smart_onoff=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		srv_enable
	FROM
		services_services
	WHERE
		srv_service = 'smartd'
	ORDER BY
		-id
	LIMIT 1
	")

	if [ "$smart_onoff" = "1" ]
	then
		smart_enabled="start on boot."
	fi

	section_header "SMARTD Boot Status"
	echo "SMARTD will $smart_enabled"
	section_footer

	section_header "SMARTD Run Status"
	if is_linux; then
		systemctl status smartd
	else
		service smartd-daemon onestatus
	fi
	section_footer

	section_header "Scheduled SMART Jobs"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} -line "
	SELECT *
	FROM tasks_smarttest
	WHERE id >= '1'
	ORDER BY +id"
	section_footer

	section_header "Disks being checked by SMART"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} -line "
	SELECT *
	FROM tasks_smarttest_smarttest_disks
	WHERE id >= '1'
	ORDER BY +id"
	section_footer

	section_header "smartctl -a"
	if [ -f /tmp/smart.out ]; then
		rm -f /tmp/smart.out
	fi

	if is_linux; then
		disks=$(lsblk -ndo name | grep -v '^sr')
	else
		disks=$(sysctl -n kern.disks)
	fi

	for i in $disks
	do
    		echo /dev/$i >> /tmp/smart.out
		smartctl -a /dev/$i >> /tmp/smart.out
	done
	cat /tmp/smart.out
	${FREENAS_DEBUG_MODULEDIR}/smart/smart.nawk < /tmp/smart.out
	section_footer
}
