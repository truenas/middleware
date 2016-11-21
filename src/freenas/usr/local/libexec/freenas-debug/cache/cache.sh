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


cache_opt() { echo c; }
cache_help() { echo "Dump (AD|LDAP) Cache"; }
cache_directory() { echo "DirectoryCache"; }
cache_func()
{
	local cachetype="${1}"

	cachedir="${FREENAS_CACHEDIR}"
	directory_cachedir=

	case ${cachetype} in
		AD) directory_cachedir="${cachedir}/.ldap/.activedirectory" ;;
		LDAP) directory_cachedir="${cachedir}/.ldap/.ldap" ;;
	esac

	directory_local_users="${directory_cachedir}/.local/.users/.cache.db"
	directory_local_groups="${directory_cachedir}/.local/.users/.cache.db"
	directory_users="${directory_cachedir}/.users/.cache.db"
	directory_groups="${directory_cachedir}/.groups/.cache.db"

	if [ -f "${directory_local_users}" ]
	then
		section_header "${directory_local_users}"
		/usr/local/bin/db_stat-4.8 -d "${directory_local_users}"
		section_footer
	fi

	if [ -f "${directory_local_groups}" ]
	then
		section_header "${directory_local_groups}"
		/usr/local/bin/db_stat-4.8 -d "${directory_local_groups}"
		section_footer
	fi

	if [ -f "${directory_users}" ]
	then
		section_header "${directory_users}"
		/usr/local/bin/db_stat-4.8 -d "${directory_users}"
		section_footer
	fi

	if [ -f "${directory_groups}" ]
	then
		section_header "${directory_groups}"
		/usr/local/bin/db_stat-4.8 -d "${directory_groups}"
		section_footer
	fi

	section_header "User and Group cache dump"
	/usr/local/www/freenasUI/tools/cachetool.py dump
	section_footer
}
