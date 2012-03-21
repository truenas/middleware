#!/bin/sh

MAGIC="WINACL"

usage()
{
	cat <<-__EOF__
	Usage: $0 [options] ...
	Where option is:
	    -o owner
	    -g group
	    -d directory
__EOF__

	exit 1
}


winacl_reset()
{
	local path="${1}"

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


	echo "${path}"
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

	find "${dir}" \( -type f -o -type d \) -exec $0 ${MAGIC} {} \;
	return $?
}

main()
{
	local owner
	local group
	local dir

	local magic="${1}"
	local path="${2}"

	if [ "${magic}" = "${MAGIC}" -a -e "${path}" ]
	then
		winacl_reset "${path}"
		return 0

	elif [ "$#" -lt "2" ]
	then
		usage
	fi

	while getopts "o:g:d:" opt
	do
		case "${opt}" in 
			o) owner="${OPTARG}" ;;
			g) group="${OPTARG}" ;;
			d) dir="${OPTARG}" ;;
			:|\?) usage ;;
		esac
	done

	if [ -n "${owner}" -a -n "${group}" ]
	then
		chown -R "${owner}:${group}" "${dir}"

	elif [ -n "${owner}" ]
	then
		chown -R "${owner}" "${dir}"

	elif [ -n "${group}" ]
	then
		chgrp -R "${group}" "${dir}"
	fi

	reset_permissions "${dir}"
	return $?
}

main $*
