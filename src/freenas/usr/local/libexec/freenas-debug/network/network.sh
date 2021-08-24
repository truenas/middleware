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
	for i in $(ifconfig -l); do
		echo
		ifconfig -vvv ${i}
		ifconfig ${i} | grep -q '\bUP\b'
		iface_up=$?
		echo

		if [ "$iface_up" -eq 0 ]; then
			ips=$(ifconfig ${i}|grep '\binet\b'|awk '{ print $2 }'|xargs)
			ips6=$(ifconfig ${i}|grep '\binet6\b'|awk '{ print $2 }'|xargs)

			if [ -n "${ips}" ]; then
				for ip in ${ips}; do
					gw=$(route -n show -inet ${ip}|grep gateway|xargs)
					if [ -n "${gw}" ]; then
						echo "${ip} gateway ${gw}"
					fi
				done
			fi

			if [ -n "${ips6}" ]; then
				for ip6 in ${ips6}; do
					gw=$(route -n show -inet6 ${ip6}|grep gateway|xargs)
					if [ -n "${gw}" ]; then
						echo "${ip6} gateway ${gw}"
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
			int_options as 'Options'
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
	route -n show default|grep gateway|awk '{ print $2 }'
	section_footer

	section_header "Routing tables (netstat -nrW)"
	netstat -nrW
	section_footer

	section_header "ARP entries (arp -an)"
	arp -an
	section_footer

	section_header "mbuf statistics (netstat -m)"
	netstat -m
	section_footer

	section_header "Interface statistics (netstat -in)"
	netstat -in
	section_footer

	section_header "protocols - 'netstat -p protocol -s'"
	for proto in ip arp udp tcp icmp; do
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
