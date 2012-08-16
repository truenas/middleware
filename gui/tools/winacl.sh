#!/bin/sh
#- 
# Copyright (c) 2012 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
#####################################################################

usage()
{
	cat <<-__EOF__
	Usage: $0 [options] ...
	Where option is:
	    -o <owner>
	    -g <group>
	    -p <path>
	    -f <filemode>
	    -d <directorymode>
	    -r
	    -v
__EOF__

	exit 1
}

get_version()
{
	uname -r | cut -f1 -d.
}

winacl_reset()
{
	local path="${WINACL_PATH}"

	local owner_access
	local owner_inherit
	if [ -d "${path}" ]
	then
		owner_access="rwxpdDaARWcCo"
		owner_inherit="fd"
	else
		owner_access="rwxpdDaARWcCo"
		owner_inherit=""
	fi


	local group_access
	local group_inherit
	if [ -d "${path}" ]
	then
		group_access="rxs"
		group_inherit="fd"
	else
		group_access="rxs"
		group_inherit=""
	fi

	local everyone_access
	local everyone_inherit
	if [ -d "${path}" ]
	then
		everyone_access="rxaRcs"
		everyone_inherit="fd"
	else
		everyone_access="rxaRcs"
		everyone_inherit=""
	fi

	local owner_entry="owner@:${owner_access}:${owner_inherit}:allow"
	local group_entry="group@:${group_access}:${group_inherit}:allow"
	local everyone_entry="everyone@:${everyone_access}:${everyone_inherit}:allow"

	${WINACL_VFUNC} "${path}"
	eval "setfacl -b ${path}"

	eval "setfacl -a 0 ${group_entry} ${path}"
	eval "setfacl -a 1 ${everyone_entry} ${path}"
	eval "setfacl -a 2 ${owner_entry} ${path}"

	local count="$(eval getfacl ${path}|awk '{ print $1 }'|grep -v '^#'|wc -l|xargs)"
	for i in $(jot ${count} 0)
	do
		if [ ${i} -gt 2 ]
		then
			eval "setfacl -x 3 ${path}"
		fi
	done
}


change_acls()
{
	${WINACL_VFUNC} "find ${WINACL_PATH} \( -type f -o -type d \) -exec $0 -d {} \;"
	eval "find ${WINACL_PATH} \( -type f -o -type d \) -exec $0 -p {} \;"
	return $?
}


_change_owner()
{
	${WINACL_VFUNC} chown ${WINACL_FLAGS} ${WINACL_OWNER} ${WINACL_PATH}
	eval "chown ${WINACL_FLAGS} ${WINACL_OWNER} ${WINACL_PATH}"
	return $?
}


_change_group()
{
	${WINACL_VFUNC} chgrp ${WINACL_FLAGS} ${WINACL_GROUP} ${WINACL_PATH}
	eval "chgrp ${WINACL_FLAGS} ${WINACL_GROUP} ${WINACL_PATH}"
	return $?
}


_change_owner_group()
{
	${WINACL_VFUNC} chown ${WINACL_FLAGS} ${WINACL_OWNER}:${WINACL_GROUP} ${WINACL_PATH}
	eval "chown ${WINACL_FLAGS} ${WINACL_OWNER}:${WINACL_GROUP} ${WINACL_PATH}"
	return $?
}


change_owner_group()
{
	if [ -n "${WINACL_OWNER}" -a -n "${WINACL_GROUP}" ]
	then
		_change_owner_group

	elif [ -n "${WINACL_OWNER}" ]
	then
		_change_owner

	elif [ -n "${WINACL_GROUP}" ]
	then
		_change_group
	fi
}

change_permissions()
{
	if [ -n "${WINACL_FMODE}" -a -n "${WINACL_DMODE}" ]
	then
		${WINACL_VFUNC} "find ${WINACL_PATH} \
			\( -type f -a -exec chmod ${WINACL_FLAGS} ${WINACL_FMODE} {} \; \) -o \
			\( -type d -a -exec chmod ${WINACL_FLAGS} ${WINACL_DMODE} {} \; \)"
		eval "find ${WINACL_PATH} \
			\( -type f -a -exec chmod ${WINACL_FLAGS} ${WINACL_FMODE} {} \; \) -o \
			\( -type d -a -exec chmod ${WINACL_FLAGS} ${WINACL_DMODE} {} \; \)"

	elif [ -n "${WINACL_DMODE}" ]
	then
		${WINACL_VFUNC} "find ${WINACL_PATH} \
			\( -type d -a -exec chmod ${WINACL_FLAGS} ${WINACL_DMODE} {} \; \)"
		eval "find ${WINACL_PATH} \
			\( -type d -a -exec chmod ${WINACL_FLAGS} ${WINACL_DMODE} {} \; \)"

	elif [ -n "${WINACL_FMODE}" ]
	then	
		${WINACL_VFUNC} "find ${WINACL_PATH} \
			\( -type f -a -exec chmod ${WINACL_FLAGS} ${WINACL_FMODE} {} \; \)"
		eval "find ${WINACL_PATH} \
			\( -type f -a -exec chmod ${WINACL_FLAGS} ${WINACL_FMODE} {} \; \)"

	fi

	return $?
}

main()
{
	local owner
	local group
	local path 
	local fmode
	local dmode
	local major
	local verbose=0
	local recursive=0

	if [ "$#" -lt "2" ]
	then
		usage
	fi

	while getopts "o:g:p:f:d:rv" opt
	do
		case "${opt}" in 
			o) owner="${OPTARG}" ;;
			g) group="${OPTARG}" ;;
			p) path="${OPTARG}" ;;
			f) fmode="${OPTARG}" ;;
			d) dmode="${OPTARG}" ;;
			r) recursive=1 ;;
			v) verbose=1 ;;
			:|\?) usage ;;
		esac
	done

	WINACL_PATH="'${path}'"
	if [ -z "${path}" ]
	then
		usage
	fi
	export WINACL_PATH

	major=$(get_version)

	if [ "${CHANGE_ACLS}" = "1" ]
	then
		winacl_reset
	fi

	WINACL_OWNER=""
	if [ -n "${owner}" ]
	then
		WINACL_OWNER="'${owner}'"
	fi
	export WINACL_OWNER

	WINACL_GROUP=""
	if [ -n "${group}" ]
	then
		WINACL_GROUP="'${group}'"
	fi
	export WINACL_GROUP

	WINACL_FMODE="0664"
	if [ -n "${fmode}" ]
	then
		WINACL_FMODE="${fmode}"
	fi
	export WINACL_FMODE

	WINACL_DMODE="0775"
	if [ -n "${dmode}" ]
	then
		WINACL_DMODE="${dmode}"
	fi
	export WINACL_DMODE

	WINACL_VFUNC=":"
	if [ "${verbose}" = "1" ] 
	then
		WINACL_VFUNC="echo"
	fi
	export WINACL_VFUNC

	WINACL_FLAGS=""		
	if [ "${recursive}" = "1" ]
	then
		WINACL_FLAGS="-R"
	fi

	if [ "${verbose}" = "1" ]
	then
		WINACL_VFUNC="echo"
		WINACL_FLAGS="${WINACL_FLAGS} -vv"
	fi
	export WINACL_VFUNC WINACL_FLAGS

	change_owner_group
	if [ "${major}" -le "8" ]
	then
		change_permissions
	fi

	if [ "${recursive}" = "1" ]
	then
		export CHANGE_ACLS=1 
		change_acls
	else
		export CHANGE_ACLS=0
		winacl_reset
	fi

	if [ "${major}" -gt "8" ]
	then
		change_permissions
	fi
}


main "$@"
