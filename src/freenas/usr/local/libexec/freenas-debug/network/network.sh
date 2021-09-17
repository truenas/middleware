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


network_opt() { echo n; }
network_help() { echo "Dump Network Configuration"; }
network_directory() { echo "Network"; }
get_gw_in_linux_for_ip()
{
	gw=""
	output=$(ip route get "$1" from "$2" 2> /dev/null)
	if [ $(echo "$output" | grep -c "via") -eq 1 ]; then
		gw=$(echo "$output" | cut -d ' ' -f 5 | head -n 1)
        fi
	echo "$gw"
}
network_func()
{
	section_header "Hostname"
	hostname
	section_footer

	section_header "Hosts File (/etc/hosts)"
	sc "/etc/hosts"
	section_footer

	section_header "/etc/resolv.conf"
	sc /etc/resolv.conf 2>/dev/null
	section_footer

	section_header "Interfaces"
	for i in $(ls /sys/class/net); do
		echo
		ip address show dev "$i"
		echo -n "$(ethtool "$i" | grep -E 'Speed|Duplex|Port|Auto-')"
		grep -iq 'up' /sys/class/net/"$i"/operstate
		iface_up=$?
		echo
		if [ "$iface_up" -eq 0 ]; then
			ips=$(ip address show dev ${i} | grep '\binet\b' | awk '{ print $2 }' | cut -d'/' -f1 | xargs)
			if [ -n "${ips}" ]; then
				for ip in ${ips}; do
					gw=$(get_gw_in_linux_for_ip "8.8.8.8" "$ip")
					if [ -n "${gw}" ]; then
						echo "\tDefault IPv4 gateway: ${gw}"
					fi
				done
			fi

			ips6=$(ip address show dev ${i} | grep '\binet6\b' | awk '{ print $2 }' | cut -d'/' -f1 | xargs)
			if [ -n "${ips6}" ]; then
				for ip6 in ${ips6}; do
					gw=$(get_gw_in_linux_for_ip "2001:4860:4860::8888" "$ip6")
					if [ -n "${gw}" ]; then
						echo "\tDefault IPv6 gateway: ${gw}"
					fi
				done
			fi
		fi
	done
	section_footer

	# grab the interfaces marked critical for failover
	# if this is an HA system
	is_ha=$(midclt call failover.licensed)
	if [ "$is_ha" = "True" ]; then
		section_header "Interfaces marked critical for failover"
		ints=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} -line "
		SELECT
			int_interface as 'Interface',
			int_ipv4address as 'Node A IP',
			int_ipv4address_b as 'Node B IP',
			int_v4netmaskbit as 'CIDR',
			int_group as 'Group',
			int_vhid as 'VHID',
			int_vip as 'VIP',
			int_link_address as 'MAC address',
		FROM
			network_interfaces
		WHERE
			int_critical = 1")

		if [ -n "${ints}" ]; then
			echo "$ints"
		else
			echo "No interfaces marked critical for failover"
		fi
		section_footer
	fi

	section_header "Default Route"
	ip route show default | awk '/default/ {print $3}'
	section_footer

	section_header "Routing tables (netstat -nrW)"
	netstat -nrW
	section_footer

	section_header "Complete Routing tables (ip route show table all)"
	ip route show table all
	section_footer

	section_header "IP Rules (ip rule list)"
	ip rule list
	section_footer

	section_header "Iptables Rules (iptables-save -c)"
	iptables-save -c
	section_footer

	section_header "IPVS rules (ipvsadm -L)"
	ipvsadm -L
	section_footer

	section_header "IPSET rules (ipset --list)"
	ipset --list
	section_footer

	section_header "ARP entries (arp -an)"
	arp -an
	section_footer

	section_header "Interface statistics (ip -s addr)"
	ip -s addr
	section_footer

	section_header "protocols - 'netstat -p protocol -s'"
	for proto in ip arp udp tcp icmp ; do
		netstat -p $proto -s
	done
	section_footer

	section_header "Open connections and listening sockets (sockstat)"
	sockstat
	section_footer

	section_header "Network configuration"
	midclt call network.configuration.config | jq
	section_footer
}
