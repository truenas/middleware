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
}


winacl_reset()
{
	local path="${1}"

	echo "${path}"
	setfacl -b "${path}"
	for i in $(jot 5)
	do
		setfacl -x 0 "${path}"
	done

	setfacl -a 0 group@:rxs::allow "${path}"
	setfacl -a 1 everyone@:rxaRcs::allow "${path}"
	setfacl -a 2 owner@:rwxpdDaARWcCo::allow "${path}"
	setfacl -x 3 "${path}"
}

reset_permissions()
{
	local dir="${1}"

	find "${dir}" -exec $0 ${MAGIC} {} \;
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
