#!/bin/sh
get_physical_disks_list()
{
	sysctl -n kern.disks | tr ' ' '\n'| grep -v '^cd' \
		| sed 's/\([^0-9]*\)/\1 /' | sort +0 -1 +1n | tr -d ' '
}

mprutil_get_adapters()
{
	mprutil show adapters | grep "^/dev" | awk '{print $1}'
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

	section_header "pciconf -lvcb"
	pciconf -lvcb
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

	section_header "camcontrol devlist -v"
	camcontrol devlist -v
	section_footer

	section_header "nvmecontrol devlist"
	nvmecontrol devlist
	section_footer

	for disk in $(get_physical_disks_list)
	do
		if echo "${disk}" | egrep -q '^da[0-9]+'
		then
			section_header "camcontrol inquiry ${disk}"
			camcontrol inquiry "${disk}"
			section_footer
		elif echo "${disk}" | egrep -q '^ada[0-9]+'
		then
			section_header "camcontrol identify ${disk}"
			camcontrol identify "${disk}"
			section_footer
		fi
	done

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

	if [ -c /dev/mpr0 ]; then
		section_header "sas3flash -listall"
		sas3flash -listall
		section_footer
	fi

	if midclt call truenas.get_chassis_hardware | grep -q TRUENAS-M; then
		for nvdimm in /dev/nvdimm*; do
			section_header "M-Series NVDIMM $nvdimm"
			ixnvdimm $nvdimm
			section_footer
		done
	fi

	section_header "Enclosures (midclt call enclosure.query)"
	midclt call enclosure.query |jq .
	section_footer

	for dev in $(mprutil_get_adapters); do
		section_header "mprutil -u $dev show all"
		mprutil -u $dev show all
		section_footer

		section_header "mprutil -u $dev show iocfacts"
		mprutil -u $dev show iocfacts
		section_footer
	done
}
