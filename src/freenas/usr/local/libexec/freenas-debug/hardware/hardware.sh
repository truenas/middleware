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


get_physical_disks_list()
{
	sysctl -n kern.disks | tr ' ' '\n'| grep -v '^cd' \
		| sed 's/\([^0-9]*\)/\1 /' | sort +0 -1 +1n | tr -d ' '
}


hardware_opt() { echo h; }
hardware_help() { echo "Dump Hardware Configuration"; }
hardware_directory() { echo "Hardware"; }
hardware_func()
{
	section_header "Hardware"

	desc=$(sysctl -nd hw.machine)
	out=$(sysctl -n hw.machine)
	echo "${desc}: ${out}"

	desc=$(sysctl -nd hw.machine_arch)
	out=$(sysctl -n hw.machine_arch)
	echo "${desc}: ${out}"

	desc=$(sysctl -nd hw.model)
	out=$(sysctl -n hw.model)
	echo "${desc}: ${out}"

	desc=$(sysctl -nd hw.ncpu)
	out=$(sysctl -n hw.ncpu)
	echo "${desc}: ${out}"

	desc=$(sysctl -nd kern.smp.cpus)
	out=$(sysctl -n kern.smp.cpus)
	echo "${desc}: ${out}"

	desc=$(sysctl -nd dev.cpu.0.freq)
	freq=$(sysctl -n dev.cpu.0.freq)
	out=$(echo "scale=4;${freq}/1024"|bc|xargs printf "%0.2f")
	echo "${desc}: ${out} Ghz"

	desc="Physical Memory"
	ram=$(sysctl -n hw.physmem)
	rram=$(echo "scale=4;${ram}/1024/1024/1024"|bc|xargs printf "%0.2f")
	echo "${desc}: ${rram} GiB"

	section_footer

	section_header "pciconf -lv"
	pciconf -lv
	section_footer

	section_header "devinfo -rv"
	devinfo -rv
	section_footer

	section_header "usbconfig list"
	usbconfig list
	section_footer

	section_header "dmidecode"
	dmidecode
	section_footer

	section_header "memcontrol list"
	memcontrol list
	section_footer

	section_header "camcontrol devlist"
	camcontrol devlist
	section_footer

	for disk in $(get_physical_disks_list)
	do
		if echo "${disk}" | egrep -q '^da[0-9]+'
		then
			section_header "camcontrol inquiry ${disk}"
			camcontrol inquiry "${disk}"
			section_footer
		fi
	done

	for disk in $(get_physical_disks_list)
	do
		if echo "${disk}" | egrep -q '^ada[0-9]+'
		then
			section_header "camcontrol identify ${disk}"
			camcontrol identify "${disk}"
			section_footer
		fi
	done

	if [ -c /dev/ipmi0 ]
	then
		for list_type in sel sdr
		do
			section_header "ipmitool $list_type list"
			ipmitool $list_type list
			section_footer
		done
	fi

	if which getencstat > /dev/null
	then
		section_header "getencstat -V /dev/ses*"
		getencstat -V /dev/ses*
		section_footer
	fi

	if [ -c /dev/mps0 ]; then
		section_header "sas2flash -listall"
		sas2flash -listall
		section_footer
	fi
}
