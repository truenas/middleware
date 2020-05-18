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
    local onoff

    onoff=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
        SELECT
                srv_enable
        FROM
                services_services
        WHERE
                srv_service = 'iscsitarget'
        ORDER BY
                -id
        LIMIT 1
        ")

    enabled="not start on boot."
    if [ "${onoff}" = "1" ]; then
        enabled="will start on boot."
    fi

    section_header "iSCSI Boot Status"
    echo "iSCSI will ${enabled}"
    section_footer

    section_header "iSCSI Run Status"
    if is_linux; then
        systemctl status scst
    else
    	service ctld onestatus
    fi
    section_footer
	
    alua_enabled=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		iscsi_alua
	FROM
		services_iscsitargetglobalconfiguration
    ")

    if [ "${alua_enabled}" = "0" ]; then
        section_header "iSCSI ALUA Status"
        echo "ALUA is DISABLED"
    fi

    if [ "${alua_enabled}" = "1" ]; then
        section_header "iSCSI ALUA Status"
        echo "ALUA is ENABLED"
    fi

    if is_linux; then
        section_header "/etc/scst.conf"
        sed -e 's/\(IncomingUser.*"\)\(.*\)\("\)/\1\*****\3/#' -e 's/\(OutgoingUser.*"\)\(.*\)\("\)/\1\*****\3/#' /etc/scst.conf
        section_footer

        section_header "SCST Device Handlers"
        scstadmin -list_handler
        section_footer

        section_header "SCST Devices"
        scstadmin -list_device
        section_footer

        section_header "SCST Drivers"
        scstadmin -list_driver
        section_footer

        section_header "SCST iSCSI Targets"
        scstadmin -list_target -driver iscsi
        section_footer

        section_header "SCST Active Sessions"
        scstadmin -list_sessions
        section_footer

        section_header "SCST Core Attributes"
        scstadmin -list_scst_attr
        section_footer
    else
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
    fi
}
