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

	section_header "smartctl output"
	rm -f /tmp/smart.out 2>/dev/null

	if is_linux; then
		# from /proc/devices
		# only care about sd/vd/nvme major numbers
		# sd* = 8 - 135
		# vd* (virtio) = 254
		# nvmeXnY* = 259
		include="8,65,66,67,68,69,70,71,128,129,130,131,132,133,134,135,254,259"
		disks=$(lsblk -ndo name -I $include)
	else
		disks=$(sysctl -n kern.disks)
	fi

	# SAS to SATA interposers could be involed. Unfortunately,
	# there is no "easy" way of identifying that there is
	# one involved without doing some extravagant reading of
	# specific VPD pages from the device itself. Even doing
	# that is fraught with errors because the interposer creates
	# those pages, sometimes not creating them at all.
	# So, instead, we'll try to tell smartctl to do the translation
	# and if it fails (which it will on proper SAS devices) then
	# we'll try to run it without translation
	for i in $disks; do
		case "$i" in
		    nvd*)
			ns=$(nvmecontrol nsid $i | awk '{print $1}')
			output=$(smartctl -a /dev/$ns)
		        msg="(NVME DEVICE DETECTED)"
		        # double-quotes are important here to
		        # maintain original formatting
		        echo "/dev/$ns $msg" >> /tmp/smart.out
		        echo "$output" >> /tmp/smart.out
		        echo "" >> /tmp/smart.out
		    ;;
		    da*|sd*|vd*)
			# try with translation first
			msg="(USING TRANSLATION)"
			output=$(timeout 3 smartctl -a -d sat /dev/$i)
			rc=$?
			if [ $rc -ne 0 ]; then
			    if [ $rc -eq 124 ]; then
				# timeout returns 124 rc when
				# the called command is terminated
				output="TIMEOUT"
				msg="(DEVICE TOOK TOO LONG TO RESPOND)"
			    else
			        # oops try without translation
			        output=$(smartctl -a /dev/$i)
			        msg="(NOT USING TRANSLATION)"
			    fi
			fi
			# double-quotes are important here to
			# maintain original formatting
			echo "/dev/$i $msg" >> /tmp/smart.out
			echo "$output" >> /tmp/smart.out
			echo "" >> /tmp/smart.out
		    ;;
	            nvme*)
			# linux returns nvmeXnsY devices by
			# default so catch it here.
			output=$(smartctl -a /dev/$i)
			msg="(NVME DEVICE DETECTED)"
			# double-quotes are important here to
			# maintain original formatting
			echo "/dev/$i $msg" >> /tmp/smart.out
			echo "$output" >> /tmp/smart.out
			echo "" >> /tmp/smart.out
		    ;;
		esac
	done
	cat /tmp/smart.out
	${FREENAS_DEBUG_MODULEDIR}/smart/smart.nawk < /tmp/smart.out
	section_footer
}
