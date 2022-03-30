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


hardware_opt() { echo h; }
hardware_help() { echo "Dump Hardware Configuration"; }
hardware_directory() { echo "Hardware"; }
hardware_func()
{
	section_header "CPU and Memory information"

	echo "CPU architecture: $(uname -m)"

	echo "CPU model: $(lscpu | grep 'Model name' | cut -d':' -f 2 | sed -e 's/^[[:space:]]*//')"

	echo "Number of active CPUs: $(grep -c 'model name' /proc/cpuinfo)"

	echo "Number of CPUs online: $(lscpu -p=online | grep -v "^#" | grep -c "Y")"

	echo "Current average CPU frequency: $(lscpu | grep 'CPU MHz' | cut -d':' -f 2 | sed -e 's/^[[:space:]]*//') MHz"

	echo "Physical Memory: $(getconf -a | grep PAGES | awk 'BEGIN {total = 1} {if (NR == 1 || NR == 3) total *=$NF} END {print total / 1024 / 1024 / 1024" GiB"}')"

	section_footer

	section_header "lspci -vvvD"
	lspci -vvvD
	section_footer

	section_header "USB device information"
	cat /sys/kernel/debug/usb/devices
	section_footer

	section_header "dmidecode"
	dmidecode
	section_footer

	section_header "lsblk -o NAME,ALIGNMENT,MIN-IO,OPT-IO,PHY-SEC,LOG-SEC,ROTA,SCHED,RQ-SIZE,RA,WSAME,HCTL,PATH"
	lsblk -o NAME,ALIGNMENT,MIN-IO,OPT-IO,PHY-SEC,LOG-SEC,ROTA,SCHED,RQ-SIZE,RA,WSAME,HCTL,PATH
	section_footer

	section_header "Disk information (device.retrieve_disks_data)"
	midclt call device.retrieve_disks_data | jq
	section_footer

	section_header "sensors -j"
	sensors -j
	section_footer
}
