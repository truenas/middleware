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
# $FreeBSD$
#####################################################################


ldap_opt() { echo l; }
ldap_help() { echo "Dump LDAP Configuration"; }
ldap_func()
{
	local onoff

	#
	#	Turn on debug.log in syslog
	#
	syslog_debug_on

	#
	#	First, check if the LDAP service is enabled.
	#
	onoff=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		srv_enable
	FROM
		services_services
	WHERE
		srv_service = 'ldap'
	")

    enabled="DISABLED"
	if [ "${onoff}" = "1" ]
	then
		enabled="ENABLED"
	fi

	section_header "LDAP Status"
	echo "LDAP is ${enabled}"
	section_footer

	#
	#	Next, dump LDAP configuration
	#
	local IFS="|"
	read hostname basedn pwencryption anonbind ssl machinesuffix\
		groupsuffix usersuffix passwordsuffix rootbasedn<<-__LDAP__
	$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		ldap_hostname,
		ldap_basedn,
		ldap_pwencryption,
		ldap_anonbind,
		ldap_ssl,
		ldap_machinesuffix,
		ldap_groupsuffix,
		ldap_usersuffix,
		ldap_passwordsuffix,
		ldap_rootbasedn

	FROM
		services_ldap

	ORDER BY
		-id

	LIMIT 1
	")
__LDAP__
	
	IFS="
"

	section_header "LDAP Settings"
	cat<<-__EOF__
	HOSTNAME:               ${hostname}
	BASEDN:                 ${basedn}
	PWENCRYPTION:           ${pwencryption}
	ANONBIND:               ${anonbind}
	SSL:                    ${ssl}
	MACHINESUFFIX:          ${machinesuffix}
	GROUPSUFFIX:            ${groupsuffix}
	USERSUFFIX:             ${usersuffix}
	PASSWORDSUFFIX:         ${passwordsuffix}
	ROOTBASEDN:             ${rootbasedn}
__EOF__
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
	#	Dump LDAP configuration
	#
	section_header "${LDAP_CONF}"
	cat "${LDAP_CONF}"
	section_footer

	#
	#	Dump NSS configuration
	#
	section_header "${NSS_LDAP_CONF}"
	cat "${NSS_LDAP_CONF}"
	section_footer

	#
	#	Dump LDAP users and groups
	#
	section_header "LDAP Users and Groups"
	section_header "Users"
	getent passwd
	section_header "Groups"
	getent group
	section_footer

	#
	#	Dump cache info
	#
	cache_func "LDAP"

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
