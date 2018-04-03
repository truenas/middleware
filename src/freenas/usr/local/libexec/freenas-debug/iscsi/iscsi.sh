#!/bin/sh
#+
# Copyright 2013 iXsystems, Inc.
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


iscsi_opt() { echo i; }
iscsi_help() { echo "Dump iSCSI Configuration"; }
iscsi_directory() { echo "iSCSI"; }
iscsi_func()
{
	#
	#	If iSCSI is disabled, exit.
	#

	iscsi_enabled=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		srv_enable	
	FROM
		services_services
	WHERE
		srv_service = 'iscsitarget'
	")

	if [ "${iscsi_enabled}" = "0" ]
	then
		section_header "iSCSI Status"
		echo "iSCSI is DISABLED"
		exit 0
	fi

	alua_enabled=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		iscsi_alua
	FROM
		services_iscsitargetglobalconfiguration
	")

	if [ "${alua_enabled}" = "0" ]
	then
		section_header "iSCSI ALUA Status"
		echo "ALUA is DISABLED"
	fi

	if [ "${alua_enabled}" = "1" ]
	then
		section_header "iSCSI ALUA Status"
		echo "ALUA is ENABLED"
	fi

	section_header "/etc/ctl.conf"
	sc "/etc/ctl.conf.shadow"
	section_footer

	section_header "ctladm devlist -v"
	ctladm devlist -v
	section_footer

	section_header "ctladm islist"
	ctladm islist
	section_footer

	section_header "ctladm portlist -v"
	ctladm portlist -v
	section_footer

	section_header "ctladm port -l"
	ctladm port -l
	section_footer
}
