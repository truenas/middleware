#!/bin/sh
zfs_opt() { echo z; }
zfs_help() { echo "Dump ZFS Configuration"; }
zfs_directory() { echo "ZFS"; }
zfs_getacl()
{
	local ds="${1}"
	local mp
	local mounted

	mounted=$(zfs get -H -o value mounted "${ds}")
	if [ "${mounted}" == "-" ] || [ "${mounted}" == "no" ]; then
		return 0
	fi

	mp=$(zfs get -H -o value mountpoint "${ds}")
	echo "Mountpoint ACL: ${ds}"
	if [ "${mp}" != "legacy" ] && [ "${mp}" != "-" ]; then
		getfacl "${mp}" 2>/dev/null
	fi
	return 0
}

zfs_func()
{
	section_header "zfs periodic snapshot"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} -line "
	SELECT *
	FROM storage_task
	WHERE id >= '1'
	ORDER BY +id"
	section_footer

	section_header "zfs replication"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} -line "
	SELECT *
	FROM storage_replication
	WHERE id >= '1'
	ORDER BY +id"
	section_footer

	section_header "zpool scrub"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} -line "
	SELECT *
	FROM storage_scrub
	WHERE id >= '1'
	ORDER BY +id"
	section_footer
	
	section_header "zpool list -v"
	zpool list -v
	section_footer

	section_header "zfs list -ro space,refer,mountpoint"
	zfs list -ro space,refer,mountpoint
	section_footer

	section_header "zpool status -v"
	zpool status -v
	section_footer

	section_header "zpool history"
	zpool history
	section_footer

	section_header "zpool history -i | tail -n 1000"
	zpool history -i | tail -n 1000
	section_footer

	section_header "zpool get all"
	pools=$(zpool list -H|awk '{ print $1 }'|xargs)
	for p in ${pools}
	do
		section_header "${p}"
		zpool get all ${p}
		section_footer
	done
	section_footer

	section_header "zfs list -t snapshot"
	zfs list -t snapshot -o name,used,available,referenced,mountpoint,freenas:state
	section_footer

	section_header "zfs get all"
	zfs list -o name -H | while read -r s
	do
		section_header "${s}"
		zfs get all "${s}"
		zfs_getacl "${s}"
		section_footer
	done
	section_footer

	section_header  "kstat"
	sysctl kstat.zfs.misc.fletcher_4_bench
	sysctl kstat.zfs.misc.vdev_raidz_bench
	sysctl kstat.zfs.misc.dbgmsg
	for pool in $(zpool list -Ho name); do
		sysctl kstat.zfs.${pool}.misc.state
		sysctl kstat.zfs.${pool}.multihost
		sysctl kstat.zfs.${pool}.txgs
	done
	section_footer
}
