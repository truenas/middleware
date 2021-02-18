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


system_opt() { echo t; }
system_help() { echo "Dump System Information"; }
system_directory() { echo "System"; }
system_func()
{
	section_header "uptime"
	uptime
	section_footer

	section_header "date"
	date
	section_footer

	section_header "ntpq -c rv"
	ntpq -c rv
	section_footer

	section_header "ntpq -pwn"
	ntpq -pwn
	section_footer

	if is_linux; then
		section_header "ps -auxwwf"
		ps -auxwwf
	else
		section_header "ps -auxwwd"
		ps -auxwwd
	fi
	section_footer

	section_header "mount"
	mount
	section_footer

	section_header "df -T -h"
	df -T -h
	section_footer

	if is_linux; then
		section_header "swapon -s"
		swapon -s
		section_footer

		section_header "lsmod"
		lsmod
		section_footer

		section_header "dmesg -Tx"
		dmesg -Tx
		section_footer

		section_header "vmstat"
		vmstat
		section_footer

		section_header "top -SHbi -d1 -n2"
		top -SHbi -d1 -n2
		section_footer
	else
		section_header "swapinfo -h"
		swapinfo -h
		section_footer

		section_header "kldstat"
		kldstat
		section_footer

		section_header "dmesg -Tx"
		dmesg -a
		section_footer

		section_header "vmstat -ia"
		vmstat -ia
		section_footer

		section_header "top -SHIwz -d 2"
		top -SHIwz -d 2
		section_footer

		section_header "procstat -akk"
		procstat -akk
		section_footer

		section_header "vmstat -m"
		vmstat -m
		section_footer

		section_header "vmstat -z"
		vmstat -z
		section_footer

		section_header "beadm list"
		beadm list
		section_footer
	fi

	section_header "Alert System"
	midclt call alert.list | jq .
	section_footer

	section_header "Dump configuration"
	midclt call system.general.config | jq 'del(.ui_certificate.privatekey)'
	midclt call system.advanced.config | jq 'del(.sed_user, .sed_passwd)'
	section_footer

	section_header "Middleware Jobs - 'midclt call core.get_jobs'"
	midclt call core.get_jobs '[["state", "!=", "SUCCESS"]]' | jq .
	section_footer

	section_header "Middleware Asyncio Loop Tasks - 'midclt call core.get_tasks'"
	midclt call core.get_tasks | jq .
	section_footer

	section_header "Middleware Threads - 'midclt call core.threads_stacks'"
	midclt call core.threads_stacks | jq .
	section_footer

	if [ -f /data/license ]; then
		section_header "License"
		cat /data/license
		echo 'checksum'
		md5 /data/license
		echo 'Illuminated License'
		python -c \
			'from licenselib.license import License; import sys,pprint;\
			a=License.load(sys.argv[1]); pprint.pprint (a, width=43)' \
			`cat /data/license`
		section_footer
	fi

	ret1=$(midclt call system.is_enterprise)
	if [ "x${ret1}" = "xTrue" ]; then
		ret2=$(midclt call failover.status)
		section_header "HA db journal status"
		if [ "x${ret2}" != "xSINGLE" ]; then
			if [ -s /data/ha-journal ]; then
				echo "Warning: database sync journal has entries"
			else
				echo "Database sync journal normal"
			fi
		else
			echo "Non-HA TrueNAS system detected"
		fi
		section_footer
	fi

	if [ "x${ret1}" = "xFalse" ];
	then
		if [ "x${ret2}" != "xSINGLE" ];
		then
			section_header "hactl output"
			hactl
			section_footer
		else
			echo "Non-HA TrueNAS system detected"
		fi
	fi

	section_header "Failed updates /data/update.failed"
	sc /data/update.failed
	section_footer
}	
