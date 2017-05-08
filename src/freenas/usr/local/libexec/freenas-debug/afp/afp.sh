#!/bin/sh
#+
# Copyright 2017 iXsystems, Inc.
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

afp_opt() { echo f; }
afp_help() { echo "Dump AFP Configuration"; }
afp_directory() { echo "AFP"; }
afp_func()
{
	onoff=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		srv_enable
	FROM
		services_services
	WHERE
		srv_service = 'afp'
	ORDER BY
		-id
	LIMIT 1
	")

	enabled="DISABLED"
	if [ "${onoff}" = "1" ]
	then
		enabled="ENABLED"
	fi

	section_header "AFP Status"
	echo "AFP is ${enabled}"
	section_footer

	#
	#	Dump AFP version info
	#
	section_header "afpd -V"
	afpd -V
	section_footer

	#
	#	Dump AFP configuration
	#
	section_header "/usr/local/etc/afp.conf"
	sc /usr/local/etc/afp.conf
	section_footer

	local IFS="|"

	#
	#       Dump AFP shares
	#
	section_header "AFP Shares & Permissions"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		afp_path,
		afp_name
	FROM
		sharing_afp_share
	ORDER BY
		-id
	" | while read -r afp_path afp_name
	do
		section_header "${afp_name}:${afp_path}"
		ls -ld "${afp_path}"
		printf "\n"
		getfacl "${afp_path}"
		printf "\n"
	done
	section_footer
}
