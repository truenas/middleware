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


ipmi_opt() { echo I; }
ipmi_help() { echo "Dump IPMI Configuration"; }
ipmi_directory() { echo "IPMI"; }
ipmi_func()
{
	#
	#	Let's check if the character device exists.
	#	We make this check because the x-series
	#	doesn't have an internal /dev/ipmi device
	#	If the /dev/ipmi0 doesn't exist, we prevent
	#	the script from trying to run all the commands
	#
	
	section_header "ipmitool sel elist && ipmitool sdr elist"
	if [ -c /dev/ipmi0 ]
        then
               for list_type in sel sdr
               do
                       ipmitool $list_type elist
                       section_footer
               done
	else
		echo "/dev/ipmi0 device doesn't exist!"
		echo "This is expected behavior on an x-series appliance!"
		exit 0
        fi
	
	section_header "ipmitool lan print"
	ipmitool lan print
	section_footer

	section_header "ipmitool sensor"
	ipmitool sensor
	section_footer

	section_header "ipmitool mc info"
	ipmitool mc info
	section_footer

	section_header "ipmitool sel time get"
	ipmitool sel time get
	section_footer

	section_header "System Time - 'date'"
	date
	section_footer
}
