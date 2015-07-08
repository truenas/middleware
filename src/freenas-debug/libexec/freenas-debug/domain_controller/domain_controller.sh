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


domain_controller_opt() { echo D; }
domain_controller_help() { echo "Dump Domain Controller Configuration"; }
domain_controller_directory() { echo "DomainController"; }
domain_controller_func()
{
	local realm
	local domain
	local role
	local dns_backend
	local dns_forwarder
	local forest_level
	local krb_realm
	local kdc
	local admin_server
	local kpasswd_server
	local onoff
	local enabled="DISABLED"


	#
	#	First, check if the Domain Controller service is enabled.
	#
	onoff=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		srv_enable
	FROM
		services_services
	WHERE
		srv_service =  'domaincontroller'
	ORDER BY
		-id

	LIMIT 1
	")

	enabled="DISABLED"
	if [ "${onoff}" = "1" ]
	then
		enabled="ENABLED"
	fi

	section_header "Domain Controller Status"
	echo "Domain Controller is ${enabled}"
	section_footer

	#
	#	Next, dump Domain Controller configuration
	#
	local IFS="|"
	read realm domain role dns_backend dns_forwarder forest_level \
		krb_realm kdc admin_server kpasswd_server <<-__DC__
	$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		sd.dc_realm,
		sd.dc_domain,
		sd.dc_role,
		sd.dc_dns_backend,
		sd.dc_dns_forwarder,
		sd.dc_forest_level,
		dk.krb_realm,
		dk.krb_kdc,
		dk.krb_admin_server,
		dk.krb_kpasswd_server
	FROM
		services_domaincontroller as sd

	INNER JOIN
		directoryservice_kerberosrealm as dk
	ON
		(sd.dc_kerberos_realm_id = dk.id)

	ORDER BY
		-sd.id

	LIMIT 1
	")
__DC__
	
	IFS="
"

	section_header "Domain Controller Settings"
	cat<<-__EOF__
	Realm:                   ${realm}
	Domain:                  ${domain}
	Role:                    ${role}
	DNS Backend:             ${dns_backend}
	DNS Forwarder:           ${dns_forwarder}
	Forst Level:             ${forest_level}
	Kerberos Realm:          ${realm}
	Kerberos KDC:            ${kdc}
	Kerberos Admin Server:   ${admin_server}
	Kerberos Kpasswd Server: ${kpasswd_server}
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
	#	Dump Domain Controller SSSD configuration
	#
	section_header "${SSSD_CONF}"
	sc "${SSSD_CONF}" | grep -iv ldap_default_authtok
	section_footer

	#
	#	Dump generated DC config file
	#
	#section_header "${AD_CONFIG_FILE}"
	#sc "${AD_CONFIG_FILE}"
	#section_footer

	#
	#	Try to generate a DC config file
	#
	#section_header "adtool get config_file"
	#adtool get config_file
	#section_footer

	#
	#	Dump Domain Controller domain info
	#
	section_header "Domain Controller Domain Info"
	net ads info
	section_footer

	#
	#	Dump wbinfo information
	#
	section_header "Domain Controller Trust Secret"
	wbinfo -t
	section_footer
	section_header "Domain Controller NETLOGON connection"
	wbinfo -P
	section_footer
	section_header "Domain Controller trusted domains"
	wbinfo -m
	section_footer
	section_header "Domain Controller all domains"
	wbinfo --all-domains
	section_footer
	section_header "Domain Controller own domain"
	wbinfo --own-domain
	section_footer
	section_footer
	section_header "Domain Controller online status"
	wbinfo --online-status
	section_footer
	section_header "Domain Controller domain info"
	wbinfo --domain-info="$(wbinfo --own-domain)"
	section_footer
	section_header "Domain Controller DC name"
	wbinfo --dsgetdcname="$(wbinfo --own-domain)"
	section_footer
	section_header "Domain Controller DC info"
	wbinfo --dc-info="$(wbinfo --own-domain)"
	section_footer

	#
	#	Dump Domain Controller users and groups
	#
	section_header "Domain Controller Users and Groups"
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
}
