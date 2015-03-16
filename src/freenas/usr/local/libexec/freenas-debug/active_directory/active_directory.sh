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


active_directory_opt() { echo a; }
active_directory_help() { echo "Dump Active Directory Configuration"; }
active_directory_directory() { echo "ActiveDirectory"; }
active_directory_func()
{
	local workgroup
	local netbiosname
	local adminname
	local domainname
	local dcname
	local pamfiles
	local onoff
	local enabled="DISABLED"


	#
	#	First, check if the Active Directory service is enabled.
	#
	onoff=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		ad_enable
	FROM
		directoryservice_activedirectory
	ORDER BY
		-id

	LIMIT 1
	")

	enabled="DISABLED"
	if [ "${onoff}" = "1" ]
	then
		enabled="ENABLED"
	fi

	section_header "Active Directory Status"
	echo "Active Directory is ${enabled}"
	section_footer

	#
	#	Next, dump Active Directory configuration
	#
	local IFS="|"
	read domainname bindname netbiosname ssl \
		unix_extensions allow_trusted_doms use_default_domain \
		dcname gcname timeout dns_timeout <<-__AD__
	$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		ad_domainname,
		ad_bindname,
		ad_netbiosname,
		ad_ssl,
		ad_unix_extensions,
		ad_allow_trusted_doms,
		ad_use_default_domain,
		ad_dcname,
		ad_gcname,
		ad_timeout,
		ad_dns_timeout

	FROM
		directoryservice_activedirectory

	ORDER BY
		-id

	LIMIT 1
	")
__AD__
	
	IFS="
"

	section_header "Active Directory Settings"
	cat<<-__EOF__
	Domain:                 ${domainname}
	Workgroup:              ${netbiosname}
	Bind name:              ${bindname}
	UNIX extensions:        ${unix_extensions}
	Trusted domains:        ${allow_trusted_doms}
	SSL:                    ${ssl}
	Timeout:                ${timeout}
	DNS Timeout:            ${dns_timeout}
	Domain controller:      ${dcname}
	Global Catalog Server:  ${gcname}
__EOF__
	section_footer

	#
	#	Dump kerberos configuration
	#
	section_header "${PATH_KRB5_CONFIG}"
	sc "${PATH_KRB5_CONFIG}" 2>/dev/null
	section_footer

	#
	#	Dump nsswitch.conf
	#
	section_header "${PATH_NS_CONF}"
	sc "${PATH_NS_CONF}"
	section_footer

	#
	#	Dump samba configuration
	#
	section_header "${SAMBA_CONF}"
	sc "${SAMBA_CONF}"
	section_footer

	#
	#	List kerberos tickets
	#
	section_header "Kerberos Tickets"
	klist
	section_footer

	#
	#	Dump Active Directory SSSD configuration
	#
	section_header "${SSSD_CONF}"
	sc "${SSSD_CONF}" | grep -iv ldap_default_authtok
	section_footer

	#
	#	Dump generated AD config file
	#
	section_header "${AD_CONFIG_FILE}"
	sc "${AD_CONFIG_FILE}"
	section_footer

	#
	#	Try to generate an AD config file
	#
	section_header "adtool get config_file"
	adtool get config_file
	section_footer

	#
	#	Dump Active Directory domain info
	#
	section_header "Active Directory Domain Info"
	net ads info
	section_footer

	#
	#	Dump Active Directory domain status
	#
	section_header "Active Directory Domain Status"
	net ads status
	section_footer

	#
	#	Dump wbinfo information
	#
	section_header "Active Directory Trust Secret"
	wbinfo -t
	section_footer
	section_header "Active Directory NETLOGON connection"
	wbinfo -P
	section_footer
	section_header "Active Directory trusted domains"
	wbinfo -m
	section_footer
	section_header "Active Directory all domains"
	wbinfo --all-domains
	section_footer
	section_header "Active Directory own domain"
	wbinfo --own-domain
	section_footer
	section_footer
	section_header "Active Directory online status"
	wbinfo --online-status
	section_footer
	section_header "Active Directory domain info"
	wbinfo --domain-info="$(wbinfo --own-domain)"
	section_footer
	section_header "Active Directory DC name"
	wbinfo --dsgetdcname="$(wbinfo --own-domain)"
	section_footer
	section_header "Active Directory DC info"
	wbinfo --dc-info="$(wbinfo --own-domain)"
	section_footer

	#
	#	Dump Active Directory users and groups
	#
	section_header "Active Directory Users and Groups"
	section_header "Using wbinfo"
	section_header "Users"
	wbinfo -u
	section_header "Groups"
	wbinfo -g
	section_header "Using getent"
	section_header "Users"
	getent passwd
	section_header "Groups"
	getent group
	section_footer

	#
	#	Dump cache info
	#
	cache_func "AD"
}
