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
	cat <<-__EOF__
	Usage: $0 [options]
	Where option in:

	    -b <jail bridge ipv4 address>
	    -d <ipv4 default gateway>
	    -i <jail ipv4 address>
	    -j <jail name>
	    -n <ipv4 network>
	    -p <jails configuration path>
	    -t <jail type>

	    -A # do all migrations
	    -D # do default migration
	    -J # do plugins jail migration
	    -N # do plugins migration
	    -P # do mountpoints migration


	Examples:
  
	# Do a default migration with default values
	migrate_pluginjail.sh -D

	# Migrate to a different jail name, dataset will remain the same
	migrate_pluginjail.sh -j newjail

	# Migrate to a new dataset, jail name will remain the same
	migrate_pluginjail.sh -p /mnt/newdataset

	# Migrate to a new network with a new jail IP address and default gateway
	migrate_pluginjail.sh -n 192.168.99.0/24 -i 192.168.99.26 -d 192.168.99.1

	# Migrate to a new network with a new jail IP address and bridge IP
	migrate_pluginjail.sh -n 192.168.99.0/24 -i 192.168.99.26 -d 192.168.99.1

	XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
	XXX                                                                XXX
	XXX For most people, a default migration is all that is necessary. XXX
	XXX Only tweak the settings if you really know what you are doing. XXX
	XXX                                                                XXX
	XXX Please be aware that any plugins you have will need to be      XXX
	XXX updated after this migration.                                  XXX 
	XXX                                                                XXX
	XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

__EOF__
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

get_jails_jailsconfiguration_count()
{
	try runsql "
	SELECT
		count(*)

	FROM
		jails_jailsconfiguration;
	"
}

get_jails_jailsconfiguration_jc_path()
{
	try runsql "
	SELECT
		jc_path

	FROM
		jails_jailsconfiguration;

	ORDER BY
		-id

	LIMIT 1;
	"
}

get_jails_jailsconfiguration_jc_network()
{
	try runsql "
	SELECT
		jc_network

	FROM
		jails_jailsconfiguration;

	ORDER BY
		-id

	LIMIT 1;
	"
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

create_warden_jail()
{
	local jc_path="${1}"
	local jc_ipv4_network="${2}"
	local jail_host="${3}"
	local jail_ipv4="${4}"
	local jail_defaultrouter_ipv4="${5}"
	local jail_bridge_ipv4="${6}"

	shift 6
	local rsync_dirs="$*"

	local jail_dir="${jc_path}/${jail_host}"
	local jail_metadir="${jc_path}/.${jail_host}.meta"

	try mkdir -p "${jail_dir}/.plugins"
	try mkdir -p "${jail_dir}/usr/pbi"

	for line in ${rsync_dirs}
	do
		local src="$(echo ${line} | cut -f1 -d':' -s)"
		local dst="$(echo ${line} | cut -f2 -d':' -s)"

		if [ -d "${src}" -a -d "${dst}" ]
		then
			try ${RSYNC} -avz "${src}/" "${dst}"
		fi
	done

	try mkdir -p "${jail_metadir}"
	try cp /etc/ix/templates/warden/jail-* "${jail_metadir}/"
	try touch "${jail_metadir}/jail-pluginjail"

	echo "${jail_host}" > "${jail_metadir}/host"
	get_next_id > "${jail_metadir}/id"
	
	sed -E -e "s|^(WTMP:)(.+)|\1 ${jc_path}|" \
		-e "s|^(JDIR:)(.+)|\1 ${jc_path}|" \
		"${WARDENCONF}" > "${WARDENCONF}.new"

	if [ "$?" = "0" -a -f "${WARDENCONF}.new" ]
	then
		try mv "${WARDENCONF}.new" "${WARDENCONF}"
	fi

	try ${WARDEN} set ipv4 ${jail_host} ${jail_ipv4}
	try ${WARDEN} set bridge-ipv4 ${jail_host} ${jail_bridge_ipv4}
	try ${WARDEN} auto ${jail_host}
}

update_warden_conf()
{
	sed -E -e "s|^(WTMP:)(.+)|\1 ${jc_path}|" \
		-e "s|^(JDIR:)(.+)|\1 ${jc_path}|" \
		"${WARDENCONF}" > "${WARDENCONF}.new"

	if [ "$?" = "0" -a -f "${WARDENCONF}.new" ]
	then
		try mv "${WARDENCONF}.new" "${WARDENCONF}"
	fi
}

do_services_pluginsjail_migration()
{
	local jc_path="${1}"
	local jc_ipv4_network="${2}"
	local jail_host="${3}"
	local jail_ipv4="${4}"
	local jail_defaultrouter_ipv4="${5}"
	local jail_bridge_ipv4="${6}"

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

	update_warden_conf "${jc_path}"

	local jail_dir="${jc_path}/${jail_host}"
	local plugins_path="$(get_services_pluginsjail_plugins_path)"
	if [ -z "${plugins_path}" ]
	then
		kill_thyself "plugins_path is null"
	fi

	create_warden_jail \
		"${jc_path}" \
		"${jc_ipv4_network}" \
		"${jail_host}" \
		"${jail_ipv4}" \
		"${jail_defaultrouter_ipv4}" \
		"${jail_bridge_ipv4}" \
		"${plugins_path}/pbi:${jail_dir}/usr/pbi"

	return 0
}

do_plugins_plugins_migration()
{
	local jail_host="${1}"

	try runsql "
	UPDATE 
		plugins_plugins

	SET
		plugin_jail = '${jail_host}';
	"

	return $?
}

do_plugins_nullmountpoint_migration()
{
	local jail_host="${1}"
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
			'${jail_host}',
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
	local jc_ipv4_network
	local jail_ipv4
	local jail_bridge_ipv4
	local jail_type
	local jail_host
	local jail_defaultrouter_ipv4
	local pluginsjail_migration
	local plugins_migration
	local nullmountpoint_migration
	local default_migration

#	if [ "$#" -le "2" ]
#	then
#		usage
#		exit 1
#	fi

	local args="$(getopt b:d:hj:n:p:t:ADJNP $*)"
	if [ "$?" != "0" ]
	then		
		usage
		exit 2
	fi

	pluginsjail_migration=0
	plugins_migration=0
	nullmountpoint_migration=0
	default_migration=0

	set -- $args
	while true
	do
		case "$1" in

		-b) jail_bridge_ipv4="${2}"
			shift
			;;

		-d) jail_defaultrouter_ipv4="${2}"
			shift
			;;

		-h) usage
			exit 0
			;;

		-i) jail_ipv4="${2}"
			shift
			;;

		-j) jail_host="${2}"
			shift
			;;

		-n) jc_ipv4_network="${2}"
			shift
			;;

		-p) jc_path="${2}"
			shift
			;;

		-t) jail_type="${2}"
			shift
			;;

		-A) pluginsjail_migration=1
			plugins_migration=1
			nullmountpoint_migration=1
			;;

		-D) default_migration=1
			;;

		-J) pluginsjail_migration=1
			;;

		-N) plugins_migration=1
			;;

		-P) nullmountpoint_migration=1
			;;

		--) break
			;;

		esac

		shift
	done

	do_backup

	trap do_error 2 3 6 9

	if [ "${default_migration}" = "1" ]
	then
		jc_path="$(get_services_pluginsjail_jail_path)"
		jc_ipv4_network="192.168.99.0/24"
		jail_host="$(get_services_pluginsjail_jail_name)"
		jail_ipv4="192.168.99.26/24"
		jail_bridge_ipv4="192.168.99.1/24"
		jail_type='pluginjail'
		pluginsjail_migration=1
		plugins_migration=1
		nullmountpoint_migration=1
	fi

	if [ -z "${jc_path}" ]
	then
		kill_thyself "jc_path is null"
	fi

	if [ -z "${jc_ipv4_network}" ]
	then
		kill_thyself "jc_ipv4_network is null"
	fi

	if [ -z "${jail_host}" ]
	then
		kill_thyself "jail_host is null"
	fi

	if [ -z "${jail_ipv4}" ]
	then
		kill_thyself "jail_ipv4 is null"
	fi

	if [ -z "${jail_defaultrouter_ipv4}" -a -z "${jail_bridge_ipv4}" ]
	then
		kill_thyself "jail_defaultrouter_ipv4 and jail_bridge_ipv4 " \
			"are both null, one of these must be set"
	fi

	if [ "${pluginsjail_migration}" = "1" ]
	then
		do_services_pluginsjail_migration \
			"${jc_path}" \
			"${jc_ipv4_network}" \
			"${jail_host}" \
			"${jail_ipv4}" \
			"${jail_defaultrouter_ipv4}" \
			"${jail_bridge_ipv4}"
	fi

	if [ "${plugins_migration}" = "1" ]
	then
		do_plugins_plugins_migration "${jail_host}"
	fi

	if [ "${nullmountpoint_migration}" = "1" ]
	then
		do_plugins_nullmountpoint_migration "${jail_host}"
	fi

	return 0
}

main $*
