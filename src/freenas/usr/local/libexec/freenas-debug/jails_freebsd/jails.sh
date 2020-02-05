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
jails_help() { echo "Dump Jail Information"; }
jails_directory() { echo "Jails"; }
jails_func()
{

	# Only run on FreeNAS.
	# Only run this on TrueNAS that is licensed for jails.
	# We do this because everytime a debug is captured
	# iocage list and iocage debug autocreate the datasets.
	# This causes mass confusion to customers and ultimately
	# ends up causing a support ticket.
	jails="$(midclt call system.feature_enabled JAILS)"

	if [ "$jails" = "True" ]; then
		section_header "jls"
		jls
		section_footer

		section_header "jls -v"
		jls -v
		section_footer

		section_header "iocage list"
		iocage list
		section_footer

		iocage debug -d "$FREENAS_DEBUG_DIRECTORY/Jails/iocage-debug"
	fi
}
