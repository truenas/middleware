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

SMBCONF=${SAMBA_CONF:-"/etc/smb4.conf"}
PATH_KRB5_CONFIG=${PATH_KRB5_CONFIG:-"/etc/krb5.conf"}
PATH_NS_CONF=${PATH_NS_CONF:-"/etc/nsswitch.conf"}

active_directory_opt() { echo a; }
active_directory_help() { echo "Dump Active Directory Configuration"; }
active_directory_directory() { echo "ActiveDirectory"; }
active_directory_func()
{
	AD_CONF=$(midclt call activedirectory.config | jq 'del(.bindpw)')
	local domainname=$(echo ${AD_CONF} | jq ".domainname")
	local onoff=$(echo ${AD_CONF} | jq ".enable")
	local enabled="DISABLED"
	local cifs_onoff

	enabled="DISABLED"
	if [ "${onoff}" == "true" ]
	then
		enabled="ENABLED"
	fi
	
	section_header "Active Directory Status"
	echo "Active Directory is ${enabled}"
	section_footer

	section_header "Active Directory Run Status"
	service winbindd status
	section_header

	#
	#	Check if SMB service is set to start on boot.
	#
	cifs_onoff=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		srv_enable
	FROM
		services_services
	WHERE
		srv_service = 'cifs'
	ORDER BY
		-id
	LIMIT 1
	")	

	cifs_enabled="not start on boot."
	if [ "$cifs_onoff" == "1" ]
	then
		cifs_enabled="start on boot."
	fi

	section_header "SMB Service Status"
	echo "SMB will $cifs_enabled"
	section_footer

	section_header "Active Directory Settings"
	echo ${AD_CONF} | jq
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
	section_header "${SMBCONF}"
	sc "${SMBCONF}"
	section_footer

	#
	#	List kerberos tickets
	#
	section_header "Kerberos Tickets - 'klist'"
	klist
	section_footer

	#
	#	List kerberos keytab entries
	#
	section_header "Kerberos Principals - 'ktutil'"
	midclt call kerberos.keytab.kerberos_principal_choices
	section_footer

	#
	#	Dump Active Directory Domain Information
	#
	if [ "${enabled}" = "ENABLED" ]
	then
	section_header "Active Directory Domain Info - 'midclt call activedirectory.domain_info'"
	midclt call activedirectory.domain_info | jq
	section_footer
	fi

	#
	#	Dump wbinfo information
	#
	section_header "Active Directory Trust Secret - 'wbinfo -t'"
	wbinfo -t
	section_footer
	section_header "Active Directory NETLOGON connection - 'wbinfo -P'"
	wbinfo -P
	section_footer
	section_header "Active Directory trusted domains - 'wbinfo -m'"
	wbinfo -m --verbose
	section_footer
	section_header "Active Directory all domains - 'wbinfo --all-domains'"
	wbinfo --all-domains
	section_footer
	section_header "Active Directory own domain - 'wbinfo --own-domain'"
	wbinfo --own-domain
	section_footer
	section_header "Active Directory online status - 'wbinfo --online-status'"
	wbinfo --online-status
	section_footer
	section_header "Active Directory domain info - 'wbinfo --domain-info=$(wbinfo --own-domain)'"
	wbinfo --domain-info="$(wbinfo --own-domain)"
	section_footer
	section_header "Active Directory DC name - 'wbinfo --dsgetdcname=${domainname}'"
	wbinfo --dsgetdcname="${domainname}"
	section_footer
	section_header "Active Directory DC info - 'wbinfo --dc-info=$(wbinfo --own-domain)'"
	wbinfo --dc-info="$(wbinfo --own-domain)"
	section_footer

	#
	#	Dump Active Directory users and groups
	#
	section_header "Active Directory Users - 'wbinfo -u'"
	wbinfo -u | head -50
	section_header "Active Directory Groups - 'wbinfo -g'"
	wbinfo -g | head -50
	section_footer

	#
	#	Dump results of testjoin
	#
	if [ "${enabled}" = "ENABLED" ]
	then
	section_header "Active Directory Join Status net -d 5 -k ads testjoin"
	net -d 5 -k ads testjoin
	section_footer
	fi

	#
	#	Dump results clockskew check
	#
	if [ "${enabled}" = "ENABLED" ]
	then
	section_header "Active Directory clockskew - midclt call activedirectory.check_clockskew"
	midclt call activedirectory.check_clockskew | jq
	section_footer
	fi

	#
	#	Dump Kerberos SPNs
	#
	if [ "${enabled}" = "ENABLED" ]
	section_header "Active Directory SPN list"
	then
	midclt call activedirectory.get_spn_list | jq
	section_footer
	fi

	#
	#	Dump idmap settings
	#
	section_header "idmap settings"
	midclt call idmap.query | jq
	section_footer
}
