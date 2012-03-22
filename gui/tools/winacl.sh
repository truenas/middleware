#!/bin/sh

MAGIC="WINACL"
VFUNC=":"

usage()
{
	cat <<-__EOF__
	Usage: $0 [options] ...
	Where option is:
	    -o owner
	    -g group
	    -d directory
	    -v
__EOF__

	exit 1
}


winacl_reset()
{
	local path="${1}"
	local func="${2}"

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

	${func} "${path}"
	setfacl -b "${path}"
	for i in $(jot 5)
	do
		setfacl -x 0 "${path}"
	done

	setfacl -a 0 "${group_entry}" "${path}"
	setfacl -a 1 "${everyone_entry}" "${path}"
	setfacl -a 2 "${owner_entry}" "${path}"
	setfacl -x 3 "${path}"
}

reset_permissions()
{
	local dir="${1}"

	${VFUNC} find "${dir}" \( -type f -o -type d \) -exec $0 ${MAGIC} {} \;
	find "${dir}" \( -type f -o -type d \) -exec $0 ${MAGIC} {} \;
	return $?
}

main()
{
	local owner
	local group
	local dir
	local verbose="0"

	local magic="${1}"
	local path="${2}"

	if [ "${magic}" = "${MAGIC}" -o "${magic}" = "${MAGIC}_v" -a -e "${path}" ]
	then
		if [ "${magic}" = "${MAGIC}_v" ]
		then
			VFUNC="echo"
		fi

		winacl_reset "${path}" "${VFUNC}"
		return 0

	elif [ "$#" -lt "2" ]
	then
		usage
	fi

	while getopts "o:g:d:v" opt
	do
		case "${opt}" in 
			o) owner="${OPTARG}" ;;
			g) group="${OPTARG}" ;;
			d) dir="${OPTARG}" ;;
			v) verbose=1 ;;
			:|\?) usage ;;
		esac
	done

	local flags="-R"
	if [ "${verbose}" = "1" ]
	then
		MAGIC="${MAGIC}_v"
		VFUNC="echo"
		flags="-Rvv"
	fi

	if [ -n "${owner}" -a -n "${group}" ]
	then
		${VFUNC} chown "${flags}" "${owner}:${group}" "${dir}"
		chown "${flags}" "${owner}:${group}" "${dir}"

	elif [ -n "${owner}" ]
	then
		${VFUNC} chown "${flags}" "${owner}" "${dir}"
		chown "${flags}" "${owner}" "${dir}"

	elif [ -n "${group}" ]
	then
		${VFUNC} chgrp "${flags}" "${group}" "${dir}"
		chgrp "${flags}" "${group}" "${dir}"
	fi

	reset_permissions "${dir}"
	return $?
}

main $*
