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
	#	Turn on debug.log in syslog
	#
	syslog_debug_on

	#
	#	First, check if the Active Directory service is enabled.
	#
	onoff=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		srv_enable
	FROM
		services_services
	WHERE
		srv_service = 'activedirectory'
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
	read workgroup netbiosname adminname domainname dcname <<-__AD__
	$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		ad_workgroup,
		ad_netbiosname,
		ad_adminname,
		ad_domainname,
		ad_dcname

	FROM
		services_activedirectory

	ORDER BY
		-id

	LIMIT 1
	")
__AD__
	
	IFS="
"

	section_header "Active Directory Settings"
	cat<<-__EOF__
	WORKGROUP:              ${workgroup}
	NETBIOS NAME:           ${netbiosname}
	ADMINNAME:              ${adminname}
	DOMAIN NAME:            ${domainname}
	DCNAME:                 ${dcname}
__EOF__
	section_footer

	#
	#	Dump kerberos configuration
	#
	section_header "${PATH_KRB5_CONFIG}"
	cat "${PATH_KRB5_CONFIG}" 2>/dev/null
	section_footer

	#
	#	Dump nsswitch.conf
	#
	section_header "${PATH_NS_CONF}"
	cat "${PATH_NS_CONF}"
	section_footer

	#
	#	Dump pam configuration
	#
	section_header "${PAM_DIR}"
	for pf in $(ls "${PAM_DIR}"|grep -v README)
	do
		section_header "${PAM_DIR}/${pf}"
		cat "${PAM_DIR}/${pf}"
		section_footer
	done
	section_footer

	#
	#	Dump samba configuration
	#
	section_header "${SMB_CONF}"
	cat "${SMB_CONF}"
	section_footer

	#
	#	List kerberos tickets
	#
	section_header "Kerberos Tickets"
	klist
	section_footer

	#
	#	Dump Active Directory NSS configuration
	#
	section_header "${NSS_LDAP_CONF}"
	cat "${NSS_LDAP_CONF}"
	section_footer

	#
	#	Dump Active Directory domain status
	#
	section_header "Active Directory Domain Status"
	net ads info
	section_footer

	#
	#	Check Active Directory trust secret
	#
	section_header "Active Directory Trust Secret"
	wbinfo -t
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

	#
	#	Include LDAP debugging
	#
	section_header "/var/log/debug.log"
	cat /var/log/debug.log
	section_footer

	#
	#	Turn off debug.log in syslog
	#
	syslog_debug_off
}
