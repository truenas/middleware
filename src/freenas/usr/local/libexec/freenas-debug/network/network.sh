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

	#
	#	Dump hosts configuration
	#
	section_header "Hosts File (/etc/hosts)"
	sc "/etc/hosts"
	section_footer

	#
	#	Dump resolver information
	#
	section_header "/etc/resolv.conf"
	sc /etc/resolv.conf 2>/dev/null
	section_footer

	section_header "Interfaces"
	for i in $(ifconfig -l)
	do
		ifconfig -v ${i}
		echo

		if $(ifconfig ${i}|grep -q '\bUP\b')
		then
			ips=$(ifconfig ${i}|grep '\binet\b'|awk '{ print $2 }'|xargs)
			ips6=$(ifconfig ${i}|grep '\binet6\b'|awk '{ print $2 }'|xargs)

			if [ -n "${ips}" ]
			then
				for ip in ${ips}
				do
					gw=$(route -n show -inet ${ip}|grep gateway|xargs)
					if [ -n "${gw}" ]
					then
						echo "${ip} gateway ${gw}"
					fi
				done
			fi

			if [ -n "${ips6}" ]
			then
				for ip6 in ${ips6}
				do
					gw=$(route -n show -inet6 ${ip6}|grep gateway|xargs)
					if [ -n "${gw}" ]
					then
						echo "${ip6} gateway ${gw}"
					fi
				done
			fi
		fi
	done
	section_footer

	section_header "Default Route"
	route -n show default|grep gateway|awk '{ print $2 }'
	section_footer

	section_header "Routing tables (netstat -nr)"
	netstat -nr
	section_footer

	section_header "ARP entries (arp -a)"
	arp -a
	section_footer

	section_header "mbuf statistics (netstat -m)"
	netstat -m
	section_footer

	section_header "Interface statistics (netstat -i)"
	netstat -i
	section_footer

	section_header "protocols"
    for proto in ip arp udp tcp icmp ; do
	netstat -p $proto -s
    done
	section_footer

	section_header "Open connections and listening sockets (sockstat)"
	sockstat
	section_footer
}
