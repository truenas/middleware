#!/bin/sh
#+
# Copyright 2015 iXsystems, Inc.
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


jails_opt() { echo j; }
jails_help() { echo "Dump jails Information"; }
jails_directory() { echo "Jails"; }
jails_func()
{
	local jc_path
	local jc_ipv4_dhcp
	local jc_ipv4_network
	local jc_ipv4_network_start
	local jc_ipv4_network_end
	local jc_ipv6_autoconf
	local jc_ipv6_network
	local jc_ipv6_network_start
	local jc_ipv6_network_end
	local jc_collectionurl
	local IFS="|"

	section_header "jails configuration"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		jc_path,
		jc_ipv4_dhcp,
		jc_ipv4_network,
		jc_ipv4_network_start,
		jc_ipv4_network_end,
		jc_ipv6_autoconf,
		jc_ipv6_network,
		jc_ipv6_network_start,
		jc_ipv6_network_end,
		jc_collectionurl
	FROM
		jails_jailsconfiguration
	ORDER BY
		-id
	LIMIT 1
	" | while read jc_path jc_ipv4_dhcp jc_ipv4_network jc_ipv4_network_start \
		jc_ipv4_network_end jc_ipv6_autoconf jc_ipv6_network \
		jc_ipv6_network_start jc_ipv6_network_end jc_collectionurl
	do
		if [ "${jc_ipv4_dhcp}" = "1" ]
		then
			jc_ipv4_dhcp="enabled"
		fi
		if [ "${jc_ipv6_autoconf}" = "1" ]
		then
			jc_ipv6_autoconf="enabled"
		fi

		cat<<-__EOF__
		Path: ${jc_path}
		IPv4 DHCP: ${jc_ipv4_dhcp}
		IPv4 Network: ${jc_ipv4_network}
		IPv4 Network Range: ${jc_ipv4_network_start}-${jc_ipv4_network_end}
		IPv6 Autoconf: ${jc_ipv6_autoconf}
		IPv6 Network: ${jc_ipv6_network}
		IPv6 Network Range: ${jc_ipv6_network_start}-${jc_ipv6_network_end}
		Collection URL: ${jc_collectionurl}
__EOF__
	done
	section_footer	

	jc_path="$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		jc_path
	FROM
		jails_jailsconfiguration
	ORDER BY
		-id
	LIMIT 1
	")"

	section_header "ls -ldF ${jc_path}"
	ls -ldF "${jc_path}"
	section_footer

	section_header "getfacl ${jc_path}"
	getfacl "${jc_path}"
	section_footer

	section_header "ls -aF ${jc_path}"
	ls -la "${jc_path}"
	section_footer

	section_header "jls"
	jls
	section_footer

	section_header "jls -v"
	jls -v
	section_footer

	section_header "warden list"
	warden list
	section_footer

	section_header "warden list -v"
	warden list -v
	section_footer

	section_header "warden.conf"
	cat /usr/local/etc/warden.conf
	section_footer

	section_header "warden template list"
	warden template list
	section_footer

	section_header "warden template list -v"
	warden template list -v
	section_footer

	local jt_name
	local jt_os
	local jt_arch
	local jt_url
	local jt_system
	local jt_readonly

	section_header "templates configuration"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		jt_name,
		jt_os,
		jt_arch,
		jt_url,
		jt_system,
		jt_readonly
	FROM
		jails_jailtemplate
	ORDER BY
		-id
	LIMIT 1
	" | while read jt_name jt_os jt_arch jt_url jt_system jt_readonly
	do
		cat<<-__EOF__
		Name: ${jt_name}
		OS: ${jt_os}
		Arch: ${jt_arch}
		URL: ${jt_url}
		System: ${jt_system}
		Readonly: ${jt_readonly}
__EOF__
	done
	section_footer	

	local jail
	local source
	local destination
	local readonly

	section_header "jail mountpoints"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		jail,
		source,
		destination,
		readonly
	FROM
		jails_jailmountpoint
	ORDER BY
		-id
	LIMIT 1
	" | while read jail source destination readonly
	do
		cat<<-__EOF__
		Jail: ${jail}
		Source: ${source}
		Destination: ${destination}
		Readonly: ${readonly}
__EOF__
	done
	section_footer

	local repourl

	section_header "plugins configuration"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		repourl
	FROM
		plugins_configuration
	ORDER BY
		-id
	LIMIT 1
	" | while read repourl
	do
		echo "URL: ${repourl}"
	done
	section_footer

	local plugin_name
	local plugin_pbiname
	local plugin_version
	local plugin_api_version
	local plugin_arch
	local plugin_enabled
	local plugin_ip
	local plugin_port
	local plugin_path
	local plugin_jail

	section_header "plugins"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		plugin_name,
		plugin_pbiname,
		plugin_version,
		plugin_api_version,
		plugin_arch,
		plugin_enabled,
		plugin_ip,
		plugin_port,
		plugin_path,
		plugin_jail
	FROM
		plugins_plugins
	ORDER BY
		-id
	LIMIT 1
	" | while read plugin_name plugin_pbiname plugin_version \
		plugin_api_version plugin_arch plugin_enabled \
		plugin_ip plugin_port plugin_path plugin_jail
	do
		section_header "${plugin_name}"
		cat<<-__EOF__
		Name: ${plugin_name}
		PBI Name: ${plugin_pbiname}
		Version: ${plugin_version}
		API Version: ${plugin_api_version}
		Arch: ${plugin_arch}
		Enabled: ${plugin_enabled}
		IPv4 Address: ${plugin_ip}
		Port: ${plugin_port}
		Path: ${plugin_path}
		Jail: ${plugin_jail}
__EOF__
		section_footer
	done
	section_footer
}
