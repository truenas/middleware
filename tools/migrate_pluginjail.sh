#!/bin/sh

. /etc/rc.freenas
. /usr/local/share/warden/scripts/backend/functions.sh

BACKUP_TABLES="\
services_pluginsjail \
plugins_plugins \
plugins_nullmountpoint \
jails_jailsconfiguration \
jails_nullmountpoint \
"
BACKUP_DIRECTORY="/tmp/.pjbak"

WARDEN="/usr/local/bin/warden"
WARDENCONF="/usr/local/etc/warden.conf"
RSYNC="/usr/local/bin/rsync"


runsql()
{
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "$*"
}

do_backup()
{
	try mkdir -p "${BACKUP_DIRECTORY}"

	for table in ${BACKUP_TABLES}
	do
		try runsql ".dump ${table}" > "${BACKUP_DIRECTORY}/${table}.sql"
	done
}

do_restore()
{
	for table in ${BACKUP_TABLES}
	do
		if [ -f "${table}.sql" ]
		then
			try runsql "DROP TABLE ${table}"
			try runsql < "${BACKUP_DIRECTORY}/${table}.sql"
		fi
	done

	try rm -rf "${BACKUP_DIRECTORY}"
}

usage()
{
	:
}

DIE_CODE=1
DIE_MESSAGE=

kill_thyself()
{
	local msg="${1}"
	local ret="${2}"

	if [ -n "${msg}" ]
	then
		DIE_MESSAGE="${msg}"
	fi
	if [ -n "${ret}" ]
	then
		DIE_CODE="${code}"
	fi

	kill -2 $$
}

try()
{
	local args="$*"

	if [ -n "${args}" ]
	then
		${args}
		if [ "$?" != "0" ]
		then
			kill_thyself "FAIL: \"${args}\""
		fi
	fi

	return 0
}

get_services_pluginsjail_plugins_path()
{
	try runsql "
	SELECT
		plugins_path	

	FROM
		services_pluginsjail

	ORDER BY
		-id

	LIMIT 1;
	"
}

get_services_pluginsjail_jail_path()
{
	try runsql "
	SELECT
		jail_path

	FROM
		services_pluginsjail

	ORDER BY
		-id

	LIMIT 1;
	"
}

get_services_pluginsjail_jail_name()
{
	try runsql "
	SELECT
		jail_name

	FROM
		services_pluginsjail

	ORDER BY
		-id

	LIMIT 1;
	"
}

do_services_pluginjail_migration()
{
	local jc_ipv4_network="${1}"
	local jail_ipv4="${2}"
	local jail_bridge_ipv4="${3}"

	if [ -z "${jc_ipv4_network}" ]
	then
		kill_thyself "jc_ipv4_network is null"
	fi

	if [ -z "${jail_ipv4}" ]
	then
		kill_thyself "jail_ipv4 is null"
	fi

	if [ -z "${jail_bridge_ipv4}" ]
	then
		kill_thyself "jail_bridge_ipv4 is null"
	fi

	local plugins_path="$(get_services_pluginsjail_plugins_path)"
	if [ -z "${plugins_path}" ]
	then
		kill_thyself "plugins_path is null"
	fi

	local jail_name="$(get_services_pluginsjail_jail_name)"
	if [ -z "${jail_name}" ]
	then
		kill_thyself "jail_name is null"
	fi

	local jc_path="$(get_services_pluginsjail_jail_path)"
	if [ -z "${jc_path}" ]
	then
		kill_thyself "jc_path is null"
	fi

	try runsql "
	INSERT INTO
		jails_jailsconfiguration (
		jc_path,
		jc_ipv4_network
	)
	
	VALUES (
		'${jc_path}',
		'${jc_ipv4_network}'
	);
	"

	if [ "$?" != "0" ]
	then
		kill_thyself "jails_jailsconfiguration insert failed"
	fi

	local jail_dir="${jc_path}/${jail_name}"
	local jail_metadir="${jc_path}/.${jail_name}.meta"

	try mkdir -p "${jail_dir}/usr/pbi"
	try ${RSYNC} -avz "${plugins_path}/pbi/" "${jail_dir}/usr/pbi"
	try mkdir -p "${jail_dir}/.plugins"

	try mkdir -p "${jail_metadir}"
	try cp /etc/ix/templates/warden/jail-* "${jail_metadir}/"
	try touch "${jail_metadir}/jail-pluginjail"

	echo "${jail_name}" > "${jail_metadir}/host"
	get_next_id > "${jail_metadir}/id"
	
	sed -E -e "s|^(WTMP:)(.+)|\1 ${jc_path}|" \
		-e "s|^(JDIR:)(.+)|\1 ${jc_path}|" \
		"${WARDENCONF}" > "${WARDENCONF}.new"

	if [ "$?" = "0" -a -f "${WARDENCONF}.new" ]
	then
		try mv "${WARDENCONF}.new" "${WARDENCONF}"
	fi

	try ${WARDEN} set ipv4 ${jail_name} ${jail_ipv4}
	try ${WARDEN} set bridge-ipv4 ${jail_name} ${jail_bridge_ipv4}
	try ${WARDEN} auto ${jail_name}

	return 0
}

do_plugins_plugins_migration()
{
	local jail_name="$(get_services_pluginsjail_jail_name)"
	if [ -z "${jail_name}" ]
	then
		kill_thyself "jail_name is null"
	fi

	try runsql "
	UPDATE 
		plugins_plugins

	SET
		plugin_jail = '${jail_name}';
	"

	return $?
}

do_plugins_nullmountpoint_migration()
{
	local jail_name="$(get_services_pluginsjail_jail_name)"
	if [ -z "${jail_name}" ]
	then
		kill_thyself "jail_name is null"
	fi

	local IFS="|"

	try runsql "
	SELECT
		source,
		destination
	
	FROM
		plugins_nullmountpoint;
	" | \
	while read -r source destination
	do
		try runsql "
		INSERT INTO
			jails_nullmountpoint (
			jail,
			source,
			destination
		)

		VALUES (
			'${jail_name}',
			'${source}',
			'${destination}'
		);
		"	
	done
}

clear()
{
	try runsql "DELETE FROM jails_jailsconfiguration"
	try runsql "DELETE FROM jails_nullmountpoint"
	try runsql "DELETE FROM plugins_plugins"
}


do_error()
{
	#do_restore

	if [ -n "${DIE_MESSAGE}" ]
	then
		echo "${DIE_MESSAGE}" >/dev/stderr
	fi

	exit ${DIE_CODE}
}

main()
{
	local jc_path
	local jc_ipv4_network="192.168.99.0/24"
	local jail_ipv4="192.168.99.26/24"
	local jail_bridge_ipv4="192.168.99.1/24"

#	if [ "$#" -le "2" ]
#	then
#		usage
#		exit 1
#	fi

	local args="$(getopt p: $*)"
	if [ "$?" != "0" ]
	then		
		usage
		exit 2
	fi

	set -- $args
	while true
	do
		case "$1" in
		-p) shift; jcpath="${1}" ;;
		--) shift; break ;;
		esac
	done

	do_backup

	trap do_error 2 3 6 9

	do_services_pluginjail_migration "${jc_ipv4_network}" \
		"${jail_ipv4}" "${jail_bridge_ipv4}"

	do_plugins_plugins_migration
	do_plugins_nullmountpoint_migration

	return 0
}

main $*
