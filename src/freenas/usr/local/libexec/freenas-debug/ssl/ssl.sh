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


ssl_opt() { echo s; }
ssl_help() { echo "Dump SSL Configuration"; }
ssl_directory() { echo "SSL"; }
ssl_func()
{
	ssldir="/etc/ssl"
	fndir="${ssldir}/freenas"
	cadir="${fndir}/CA"
	privdir="${cadir}/private"
	certsdir="${cadir}/certs"
	sslconf="${fndir}/openssl.conf"
	httpdpem="${fndir}/httpd.pem"

	section_header "${ssldir}"
	ls -l ${ssldir}
	section_footer

	section_header "${fndir}"
	ls -l ${fndir}
	section_footer

	section_header "${cadir}"
	ls -l ${cadir}
	section_footer

	section_header "${privdir}"
	ls -l ${privdir}
	section_footer

	section_header "${certsdir}"
	ls -l ${certsdir}
	section_footer

	section_header "${sslconf}"
	sc ${sslconf}
	section_footer

	section_header "${httpdpem}"
	sc ${httpdpem}
	section_footer
}
