#!/bin/sh
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

	section_header "Disk information (device.get_disks)"
	midclt call device.get_disks | jq
	section_footer

	section_header "sensors -j"
	sensors -j
	section_footer

	section_header "Enclosures (midclt call enclosure.query)"
	midclt call enclosure.query |jq .
	section_footer
}
