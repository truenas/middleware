#!/bin/sh

# vim: noexpandtab ts=8 sw=4 softtabstop=4

# Setup a semi-sane environment
PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin:/rescue
export PATH
HOME=/root
export HOME
TERM=${TERM:-cons25}
export TERM

readonly SATADOM="InnoLite SATADOM"

if [ -f /etc/avatar.conf ]; then
    . /etc/avatar.conf
fi

is_truenas() {
    test "${AVATAR_PROJECT}" = "TrueNAS"
    return $?
}

#
# A set of functions to be used by the installer.
# Most of the functions have a standard format:
# <funcname> [-o output] [arguments]
# Return values are 0 or 1 depending on success
# (or whether the requested item was found).
# Any output is stored in either the requested
# output, or, in a few functions, in related files.
# Yes, this means the functions have side effect;
# this is because sh is not terribly great for
# doing multi-valued elements.  (No hashes, no
# reasonable arrays, etc, so we instead use
# the filesystem to get over that.)

#
# Missing functions:
# disk_is_mounted
#   The old install.sh simply looked at the output
#   of mount, but with GEOM and filesystem labels,
#   that doesn't necessarily mean it's mounted.

#
# Find a list of Intel raids on the system
# (only supported raid for now).  The subdisks
# for the raid will be placed in /tmp/raid-${raid}.subdisks
# E.g., /tmp/raid-r0.subdisks may have "ada0 ada1".
#
# Options:
# -o <file>	Output file for the list of raid
#		devices.  If not set, then it simply
#		returns whether there are raid devices.
#
# Arguments:
# A list of raid devices.  If this is given, it
# will use those instead of searching the system.
# This means it can determine if a disk is a raid,
# and if so get the subdisk list.
# Return value is 0 if there are raid devices,
# and 1 if there are none.

find_raid_devices() {
    local output="/dev/null"
    local opt
    local raid_device
    local raid_list

    while getopts "o:" opt
    do
	case "${opt}" in
	    o)	output="${OPTARG}" ;;
	    *)	echo "usage: find_raid_devices [-o file]" 1>&2; exit 1 ;;
	esac
    done

    shift $((OPTIND-1))
    if [ $# -gt 0 ]; then
	raid_list="$@"
    elif [ -d /dev/raid ]; then
	raid_list=$(cd /dev ; echo raid/r*)
    else
	# No raids at all
	return 1
    fi

    printf "" > ${output}

    rv=1
    for raid_device in ${raid_list}
    do
	# Get just the filename
	test -c /dev/${raid_device} || continue
	# The only raid we support is geom intel raid.
	# So that will be in /dev/raid/r*
	# What this also means is that anything that
	# does not look like "raid/r*" is by definition
	# not a raid.
	if expr "${raid_device}" : "^raid/r[0-9]*s[0-9]*" > /dev/null
	then
	    continue
	fi
	if ! expr "${raid_device}" : "^raid/r" > /dev/null
	then
	    continue
	fi
	# Since we know that it must begin with raid/r,
	# we can stick with just the basename
	raid_device=$(echo ${raid_device} | sed -e 's#^raid/##')

	# Save it to the output file
	echo "${raid_device}" >> ${output}
	# Now we want to get the list of
	# subdevices, and puti t into
	# /tmp/${raid_device}
	rm -f /tmp/raid-${raid_device}.subdisks
	echo $(graid status -s | awk '$1 == "raid/'${raid_device}'" { print $3; }') > /tmp/raid-${raid_device}.subdisks
	rv=0
    done
    return ${rv}
}

#
 # Return a list of SATA DOMs used in TrueNAS systems.
# This calls find_disk_devices, and then filters out
# only the ones we care about.
# Options:
# -o <file>	File to place the list of satadoms.
#		This is exactly like find_disk_devices.
# -R <raid_list>	File with list of raids.
#		This is passed on to find_disk_devics.
# Return values:
# 0		At least one sata-dom.
# 1		No sata-doms.
find_sata_doms() {
    local output="/dev/null"
    local raid_opt=""
    local opt

    while getopts "o:R:" opt
    do
	case "${opt}" in
	    o)	output="${OPTARG}" ;;
	    R)	raid_opt="-R ${OPTARG}" ;;
	    *)	echo "usage: find_sata_dom [-o output]" 1>&2; exit 1;;
	esac
    done
    shift $((OPTIND-1))
    if [ $# -gt 0 ]; then
	echo "usage: find_sata_dom [-o output]" 1>&2
	exit 1
    fi
    find_disk_devices ${raid_opt} -o /dev/stdout | grep "${SATADOM}" > ${output}
    return $?
}

#
# Get the size of a device.
# This will not work with pools, but will
# work with raid devices.
# Options:
# -o <file>	File to place the media size in
# Arguments:
# disk		Device name.  E.g., ada0, raid/r3
get_disk_size() {
    local opt
    local media_size
    local device
    local output="/dev/null"
    local rv=1

    while getopts "o:" opt; do
	case "${opt}" in
	    o)	output=${OPTARG} ;;
	    *)	echo "Usage: get_disk_size [-o ouptut] disk" 1>&2 ; exit 1;;
	esac
    done
    shift $((OPTIND - 1))
    if [ $# -ne 1 ]; then
	echo "usage: get_disk_size [-o output] disk" 1>&2
	exit 1
    fi
    device=$1
    printf "" > ${output}
    if diskinfo ${device} | awk '{
            capacity = $3;
            if (capacity >= 1099511627776) {
                printf("%.1f TiB", capacity / 1099511627776.0);
            } else if (capacity >= 1073741824) {
                printf("%.1f GiB", capacity / 1073741824.0);
            } else if (capacity >= 1048576) {
                printf("%.1f MiB", capacity / 1048576.0);
            } else {
                printf("%d Bytes", capacity);
        }}' > ${output}
    then
	rv=0
    fi
    return ${rv}
}

#
# Return information on a given disk device.
# The information returned includes information
# from dmesg, or "<Unknown device>" if that's
# not found, and then the size of the device.
# Options:
# -o <file>	File to place the disk information.
# Arguments:
# <disk>	Name of the disk.  E.g., ada0, raid/r0
# This does not work with zfs pools.

disk_info() {
    local opt
    local output="/dev/null"
    local media_size
    local dev_info
    local device

    while getopts "o:" opt
    do
	case "${opt}" in
	    o)	output=${OPTARG} ;;
	    *)	echo "Usage: disk_info [-o output] disk" 1>&2 ; exit 1 ;;
	esac
    done
    shift $((OPTIND - 1))

    if [ $# -ne 1 ]; then
	echo "usage: disk_info [-o output] disk" 1>&2
	exit 1
    fi
    device="$1"

    dev_info=$(dmesg | sed -n "s,^${device}: .*<\(.*\)>.*$, <\1>,p" | head -n 1)
    if [ -z "${dev_info}" ]; then
	dev_info="<Unknown device>"
    fi
    if get_disk_size ${device} > /tmp/size.$$
    then
	media_size=$(cat /tmp/size.$$)
    fi
    rm -f /tmp/size.$$
    echo "${dev_info} ${media_size}" > ${output}
    return 0
}
# Return a list of disk devices.  This is very simple,
# and does minimal filtering.  A subset of the
# pc-sysinstall disk-list code.
# It filters out cdrom devices.
# This does NOT include any raid devices
# (but it does not filter out the subdisks)!
# Options:
# -R <file>	Raid list (optional)
# -o <file>	File to place the list of disks.
# Return values:
# 0 on success, 1 on error
find_disk_devices() {
    local output="/dev/null"
    local opt
    local device
    local dev_info
    local raid_list=""
    while getopts "o:R:" opt
    do
	case "${opt}" in
	    o)	output="${OPTARG}" ;;
	    R)	raid_list="${OPTARG}" ;;
	    *)	echo "usage: find_disk_devices [-R raid_list_file] [-o file] disk [...]" 1>&2; exit 1 ;;
	esac
    done
    shift $((OPTIND-1))
    if [ $# -gt 0 ]; then
	echo "Usage:  find_disk_devices [-R raid_list_file] [-o file] disk [...]" 1>&2
	exit 1
    fi
    for device in $(sysctl -n kern.disks)
    do
	local media_size
	case "${device}" in
	    acd[0-9]*|cd[0-9]*|scd[0-9]*) continue;;
	esac
	disk_info -o /tmp/${device}.diskinfo ${device}
	dev_info=$(cat /tmp/${device}.diskinfo)
	# It may make more sense to leave this around.
	rm -f /tmp/${device}.diskinfo
	if [ -n "${raid_list}" ]; then
	    if disk_is_raid_part -R ${raid_list} -O /tmp/raid_name ${device}
	    then
		dev_info="${dev_info} (PART OF RAID $(cat /tmp/raid_name))"
	    fi
	fi
	if disk_in_pool -O /tmp/pool_names ${device}
	then
	    dev_info="${dev_info} (PART OF POOL $(cat /tmp/pool_names))"
	fi
	rm -f /tmp/raid_name
	echo "${device}	${dev_info}" >> ${output}
    done
    return 0
}

#
# Find a list of zfs pools on the system.
# This will include imported and exported
# pools.  The component disks for the pools
# will be place in /tmp/pool-${pool}.subdisks
# E.g., /tmp/pool-Stoage.subdisks.
# This can be a fairly slow process.
#
# Options:
# -o <file>	Output file for the list of pools.
#		If not set, then it simply returns
#		whether there are pools.
# -n <name>	Only look for the given name.
#		This is most important for
#		"freenas-boot".
#
# Return value is 0 if there are zfs pools
# (or if there is one matching the requested name),
# and 1 if there are none (or none matching the
# requested name).
find_zfs_pools() {
    local output="/dev/null"
    local opt
    local pool_name
    local rv=1
    local POOLS=""
    local find_pool=""

    while getopts "o:n:" opt
    do
	case "${opt}" in
	    o)	output="${OPTARG}" ;;
	    n)	pool_name="${OPTARG}" ;;
	    *)	echo "usage:  find_zfs_pools [-o file] [-n pool_name]" 1>&2 ; exit 1 ;;
	esac
    done
    shift $((OPTIND-1))
    if [ $# -ne 0 ]; then
	echo "usage: find_zfs_pools [-o file] [-n pool]" 1>&2
	exit 1
    fi

    # First look for any already-imported pools.
    if [ -n "${pool_name}" ]; then
	find_pool='$1 == "'${pool_name}'"'
    fi
    POOLS=$(zpool list -H | awk "${find_pool} { print \$1; }")
    # Next, try an import
    POOLS="${POOLS} "$(zpool import | awk " /^ *pool: ${pool_name}/ { print \$2; }")
    # Now we have pools.
    if [ "${POOLS}" = " " ]; then
	POOLS=""
    fi
    printf "${POOLS}" > ${output}
    rm -f /tmp/pool-pairs.$$
    if [ -n "${POOLS}" ]; then
	local regexp
	local disk_part
	local disk

	# If we got here, we have zfs pools.
	# If a name was requested, then it's
	# the only value in POOLS.  So return
	# value will be 0 (true).
	rv=0
	regexp="^ *name: '("$(echo ${POOLS} | sed 's/ /|/g')"|)'"
	# Now let's get the disk list.
	# We don't use find_disk_devices because we don't need
	# all of what it does.
	for disk in $(sysctl -n kern.disks)
	do
	    # First, we want to find the partition that
	    # has a zfs filesystem on it.
	    for disk_part in $(gpart show ${disk} 2>/dev/null | awk ' $4 == "freebsd-zfs" { print $3; }')
	    do
		if [ -c /dev/${disk}p${disk_part} ]; then
		    local pool
		    pool=$(eval echo $(zdb -l /dev/${disk}p${disk_part} |
			    grep -E "${regexp}" |
			    awk ' count == 0 { print $2; count++}'))
		    if [ -n "${pool}" ]; then
			echo ${disk} ${pool} >> /tmp/pool-pairs.$$
		    fi
		fi
	    done
	done
	if [ -s /tmp/pool-pairs.$$ ]; then
	    # We do this in two steps to avoid duplicate
	    # entries.  Since we don't have sort in /rescue,
	    # we use awk.
	    awk ' {
			pools[$1] = $2;
			system("rm -f /tmp/pool-" $2 ".subdisks");
		}
	END {
		for (disk in pools) {
			file = "/tmp/pool-" pools[disk] ".subdisks";
			print disk >> file
		}
	}' < /tmp/pool-pairs.$$
	fi
    fi
    rm -f /tmp/pool-pairs.$$
    return $rv
}

#
# Return 0 if the disk is part of a ZFS pool, and
# 1 if not.
# Options:
# -O <file>	File to hold the name of the pool (optional).
# Arguments:
# disk		Device to query.  Must be a disk device name
#		e.g., ada0, raid/r0
disk_in_pool() {
    local opt
    local disk
    local disk_part
    local output=/dev/null
    local rv=1

    while getopts "O:" opt
    do
	case "${opt}" in
	    O)	output=${OPTARG} ;;
	    *)	echo "Usage:  disk_in_pool [-O output] disk" 1>&2 ; exit 1 ;;
	esac
    done
    shift $((OPTIND - 1 ))

    if [ $# -ne 1 ]; then
	echo "usage: disk_in_pool [-O output] disk" 1>&2
	exit 1
    fi
    disk=$1
    printf "" > ${output}
    for disk_part in $(gpart show ${disk} 2>/dev/null | awk ' $4 == "freebsd-zfs" { print $3; }')
    do
	if [ -c /dev/${disk}p${disk_part} ]; then
	    local pool
	    pool=$(eval echo $(zdb -l /dev/${disk}p${disk_part} |
		    grep -E "^ *name: '" |
		    awk ' count == 0 { print $2; count++}'))
	    if [ -n "${pool}" ]; then
		echo ${pool} >> ${output}
		rv=0
	    fi
	fi
    done
    return ${rv}
}

#
# Return 0 if the disk is part of the known raid sets,
# and 1 if not.
# Options:
# -R <file>	List of raid sets. (Required)
# -O <file>	File to hold name of raid.  (Optional)
# Arguments:
# diskname	The disk to be tested.  E.g., ada0
# Return values:
# 0	Disk is part of a raid set
# 1	Disk is not part of one of the given raid sets.
disk_is_raid_part() {
    local output="/dev/null"
    local opt
    local raid_list
    local raid_name
    local disk_name
    local subdisk_name

    while getopts "R:O:" opt
    do
	case "${opt}" in
	    R)	raid_list="${OPTARG}" ;;
	    O)	output="${OPTARG}" ;;
	    *)	echo "usage: disk_is_raid_part -R raid_list_file [-O output] disk_name" 1>&2; exit 1;;
	esac
    done

    shift $((OPTIND-1))

    if [ $# -ne 1 -o -z "${raid_list}" ]; then
	echo "usage: disk_is_raid_part -R raid_list_file [-O output] disk_name" 1>&2
	exit 1
    fi

    printf "" > "${output}"
    disk_name="$1"

    # If the file doesn't exist, we could exit, or
    # we could just say the disk isn't part of a raid set.

    test -f "${raid_list}" || return 1
    for raid_name in $(cat "${raid_list}")
    do
	if [ -f /tmp/raid-${raid_name}.subdisks ]; then
	    for subdisk_name in $(cat /tmp/raid-${raid_name}.subdisks)
	    do
		if [ "${subdisk_name}" = "${disk_name}" ]; then
		    echo "${raid_name}" >> "${output}"
		    return 0
		fi
	    done
	fi
    done
    return 1
}

#
# Return whether the disk is a freenas disk.
# This is fairly complicated function, because we
# need to handle two different generations.
# Older generation used slices -- s1 & s2 being
# the OS, and s4 being data.
# Newer generation uses zfs and partitions:  p1
# is boot, p2 is the pool; data is in the pool.
# The pool is always named freenas-boot.
#
# N.B.  This covers FreeNAS and TrueNAS.
#
# Options: None for now.
# Arguments:  disk name (e.g., ada0, or raid/r0)
# Return values:
# 0	Disk appears to be a freenas disk
# 1	Disk does not appear to be a freenas disk
unused_disk_is_freenas() {
    local readonly disk="$1"
    local readonly mount_point=/tmp/mount.$$
    local rv=1
    local slice

    set -e
    mkdir -p ${mount_point} 

    # First let's check to see if it's got
    # slices, or a partition table.
    if [ -c /dev/${disk}s1a ]; then
	# This may be old style.  So we check
	# a couple of mount points.
	for slice in s1a s2a
	do
	    if mount -t ufs /dev/${disk}${slice} ${mount_point}
	    then
		# Mounted.  Let's see if it's a freenas-style
		# disk.
		if [ -d ${mount_point}/conf/base/etc ]; then
		    # Looks like freenas to me!
		    rv=0
		fi
		# Unmount it to clean up
		umount ${mount_point}
	    fi
	done
    elif [ -c /dev/${disk}p1 -a -c /dev/${disk}p2 ]; then
	# This may be new style.  We need to
	# see if it's part of a zfs pool
	# name freenas-boot.
	# First, let's check the partitioning.
	if gpart list ${disk} | grep -q ' type: freebsd-zfs'
	then
	    # Potentially!  Now let's try the pool name
	    # Note that we don't try to import it.
	    if zdb -l /dev/${disk}p2 | grep -q "name: 'freenas-boot'"
	    then
		# Good enough for us.
		# We could try to import it, and then mount it,
		# but importing is very heavy and slow.
		rv=0
	    fi
	fi
    fi
    return ${rv}
}

#
# Get the version(s) of freenas on one or more disks.
# This does not use disk_is_freenas, and may make it
# a moot function.
# N.B.  This will import the pool if it appears
# to be a new-style pool.  It will then export it
# when done.
#
# Options:
# -o <file>	Output file with "<fs> <device> <version> <date_in_seconds>"
#		E.g., "ufs ada0s1a FreeNAS-something 123456789".
#		(This is /etc/version from the device.)
# Arguments:
# disk		The disk.  E.g., ada0 or raid/r0
# Return value:
# 0	Disk was freenas, and version was found
# 1	Disk was not feenas, or version was not found
find_freenas_versions() {
    local opt
    local disk
    local output="/dev/null"
    local rv=1
    local slice
    local readonly raid_list="/tmp/raid-list.$$"
    local readonly mountpoint="/tmp/mount.$$"
    local version
    local timestamp

    while getopts "o:" opt
    do
	case "${opt}" in
	    o)	output="${OPTARG}" ;;
	    *)	echo "usage:  find_freenas_versions [-o output] disk" 1>&2 ; exit 1;;
	esac
    done
    shift $((OPTIND-1))
    if [ $# -lt 1 ]; then
	echo "usage: find_freenas_versions [-o output] disk" 1>&2
	exit 1
    fi
    find_raid_devices -o ${raid_list}
    set -e
    printf "" > "${output}"
    mkdir -p ${mountpoint}
    for disk
    do
	# First determine the style
	# First, let's see if this is part of a raid.
	if disk_is_raid_part -R ${raid_list} -O /tmp/disk.$$ ${disk}
	then
	    disk=raid/$(cat /tmp/disk.$$)
	fi
	rm -f /tmp/disk.$$
	if [ -c /dev/${disk}s1a ]; then
	    # Old style!
	    for slice in s1a s2a
	    do
		if test -c /dev/${disk}${slice} && mount -t ufs /dev/${disk}${slice} ${mountpoint} 2>/dev/null
		then
		    if [ -d ${mountpoint}/conf/base/etc -a -f ${mountpoint}/etc/version ]; then
			version=$(cat ${mountpoint}/etc/version)
			timestamp=$(ls -l -D %s ${mountpoint}/etc/version | awk ' { print $6; }')
			echo "ufs ${disk}${slice} ${version} ${timestamp}" >> ${output}
			rv=0
		    fi
		    umount ${mountpoint}
		fi
	    done
	elif [ "${disk}" = "zfs/freenas-boot" -o -c /dev/${disk}p2 ]; then
	    # Import the pool.  This can take a while
	    local dataset
	    # First see if this disk is a freenas zfs disk
	    if [ "${disk}" = "zfs/freenas-boot" ]; then
		:
	    elif ! zdb -l /dev/${disk}p2 | grep -q "name: 'freenas-boot'"
	    then
		continue
	    fi
	    if zpool import -N -f freenas-boot
	    then
		# Now let's go through the boot environments.
		for dataset in $(zfs list -H -r -d 1 freenas-boot/ROOT |
		    awk ' $5 == "/" || $5 == "legacy" { print $1; }')
		do
		    # Mount the dataset, and look at /etc/version
		    if mount -t zfs ${dataset} ${mountpoint}
		    then
			version=$(cat ${mountpoint}/etc/version)
			timestamp=$(ls -l -D %s ${mountpoint}/etc/version | awk ' { print $6; }')
			echo "zfs ${dataset} ${version} ${timestamp}" >> ${output}
			rv=0
			umount ${mountpoint}
		    fi
		done
		zpool export freenas-boot
	    fi
	fi
    done
    set +e

    rm -f ${raid_list}

    return ${rv}
}

#
# Back up the configuration information (and other)
# from a specific device.
# Options:
# -d <dir>	Destination to save config date.
# Argument:
# device	
# Return values:
# 0	Success
# 1	Failure or error
# Discussion:
# For old-style installs, it should be the device and slice.
# E.g., ada0s1a, or raid/r0s2a.  It will assume s4 for the
# device, and figure out the path, to mount the data partition.
# For new-style installs, it should be the selected boot environment.
# After it copies, it cleans up and removes some things that should
# not be preserved.

save_freenas_config() {
    local rv=1
    local destdir
    local opt
    local disk
    local mountpoint="/tmp/mount.$$"
    local unmount_cmd

    while getopts "d:" opt
    do
	case "${opt}" in
	    d)	destdir="${OPTARG}" ;;
	    *)	echo "Usage: save_freenas_config -d destdir disk" 1>&2 ; exit 1;;
	esac
    done
    shift $((OPTIND-1))
    if [ $# -ne 1 -o -z "${destdir}" ]; then
	echo "Usage: save_freenas_config -d destdir disk" 1>&2
	exit 1
    fi
    disk="$1"
    mkdir -p ${mountpoint}
    # The disk name needs to be "<disk>s?a".
    if [ -c /dev/${disk} ] &&
	expr "${disk}" : ".*s[12]a" > /dev/null; then
	local data_part
	data_part=$(echo "${disk}" | sed -e 's/\(.*\)s[0-9]*a/\1s4/')
	if mount -t ufs /dev/${disk} ${mountpoint} &&
	    mount -t ufs /dev/${data_part} ${mountpoint}/data
	then
	    unmount_cmd="umount ${mountpoint}/data && umount ${mountpoint}"
	fi
    elif expr "${disk}" : "^freenas-boot" > /dev/null ||
	expr "${disk}" : "^zfs/freenas-boot" > /; then
	# The disk name here is the boot environment
	zpool import -N -f freenas-boot 2> /dev/null || true
	if mount -t zfs ${disk} ${mountpoint}
	then
	    unmount_cmd="zpool export freenas-boot"
	fi
    fi
    if [ -n "${unmount_cmd}" ]; then
	# Everything is mounted, so we just grab it
	for entry in /data \
	    /conf/base/etc/hostid \
	    /root/.ssh \
	    /boot/modules \
	    /usr/local/fusionio \
	    /boot.config \
	    /boot/loader.conf.local
	do
	    if [ -e ${mountpoint}/${entry} ] ; then
		tar -C ${mountpoint} -cpf - ./${entry} |
		tar -C ${destdir} -xpf -
	    fi
	done
	# Clean up some things
	rm -rf ${destdir}/data/pkgdb

	if eval ${unmount_cmd}; then
	    rv=0
	fi
    fi
    return ${rv}
}

#
# The opposite of the above function:  restore configuration
# information to the requested location.
# Options:
# No options at this point
# Arguments:
# src	-- The directory from save_freenas_config
# dest	-- The directory to restore to.
# Return value:
# 0 on success
# 1 on error
restore_freenas_config() {
    local rv=1
    local dstdir
    local srcdir

    if [ $# -ne 2 ]; then
	echo "Usage:  restore_freenas_config src dst" 1>&2
	return 1
    fi
    # We're just copying, so use two tar's
    srcdir="$1"
    dstdir="$2"
    if tar -C "$srcdir" -cpf - . |
	tar -C "$dstdir" -xpf -
    then
	rv=0
    fi
    return ${rv}
}

#
# Pick a default FreeNAS / TrueNAS
# filesystem.  This will mount
# the filesystem(s), and then unmount
# when done.  For ZFS, this means
# that the pool will be imported.
# It then exports it when done.
# Options:
# -o <file>	File in which to put the
#		default name.  For old-style,
#		this will be <disk>s<slice>a
#		For new-style, this will
#		be the name of the clone.
# Arguments:
# device	Disk name, or a pool name.
# E.g.
# find_default_fs -o /tmp/default ada0
# find_default_fs -o /tmp/default raid/r0
# find_default_fs -o /tmp/default freenas-boot
find_default_fs() {
    local opt
    local readonly mountpoint="/tmp/default.$$"
    local output="/dev/null"
    local rv=1
    local devname

    while getopts "o:" opt
    do
	case "${opt}" in
	    o)	output="${OPTARG}" ;;
	    *)	echo "Usage: find_default_fs [-o output] devicename" 1>&2 ; exit 1 ;;
	esac
    done
    shift $((OPTIND-1))
    if [ $# -ne 1 ]; then
	echo "usage:  find_Default_fs [-o output] devicename" 1>&2
	exit 1
    fi

    mkdir -p ${mountpoint}
    devname="$1"

    # First let's check for old-style
    if [ -c /dev/${devname} -a \
	-c /dev/${devname}s1 -a \
	-c /dev/${devname}s4 ]; then
	local slice
	# Okay, let's assume old-style.
	# To decide the default slice, we
	# need to check for several things.
	# First, let's see if we have an active
	# slice on the partition.
	slice=$(gpart show ${devname} | awk ' /\[active\]/ { print $3; }')
	if [ -n "${slice}" ]; then
	    # So let's check this slice.  For GUI upgrades,
	    # this will be active, but won't have all of the right
	    # filesystem entries.
	    if mount -t ufs /dev/${devname}s${slice}a ${mountpoint}
	    then
		if [ ! -d ${mountpoint}/conf/base/etc ]; then
		    slice=$(( slice == 1 ? 2 : 1))
		    # Now let's verify this
		    umount ${mountpoint}
		    if mount -t ufs /dev/${devname}s${slice}a ${mountpoint}
		    then
			if [ ! -d ${mountpoint}/conf/base/etc ]; then
			    # Something is wrong
			    slice=
			fi
		    fi
		fi
		umount ${mountpoint} 2> /dev/null || true
		if [ -n "${slice}" ]; then
		    echo ${devname}s${slice} > ${output}
		    rv=0
		fi
	    fi
	fi
    elif [ "${devname}" = "zfs/freenas-boot" -o \
	"${devname}" = "freenas-boot" ] && zpool import -N -f freenas-boot ;then
	# We only support freenas-boot here
	# We look for the grub default.
	devname="freenas-boot"
	if mount -t zfs ${devname}/grub ${mountpoint}
	then
	    if [ -f ${mountpoint}/grub.cfg ]
	    then
		local def
		local default
		def=$(grep '^set default=' ${mountpoint}/grub.cfg |
			tail -1 |
			sed -e 's/^set default="\(.*\)"$/\1/')
		case "${def}" in
		    0)	# No default, use "default"
			default="default"
			;;
		    *FreeNAS*)
			default=$(expr "${def}" : "FreeNAS (\(.*\)) .*")
			;;
		    *)
			default=""
			;;
		esac
		if [ -n "${default}" ]; then
		    echo "${devname}/ROOT/${default}" > ${output}
		    rv=0
		fi
	    fi
	fi
	zpool export ${devname}
    else
	echo "Unknown style of disk" 1>&2
    fi
    rmdir ${mountpoint} || true
    return $rv
}

#
# Select disks on which to install.
# This is essentially all about the UI.
# It first checks to see if there are
# any raids, and if there is already an
# existing 
# Options:
# -o file	File in which to put the list of selected disks.
# No arguments.
# Return values:
# 0 -- one or more disks was selected
# 1 -- No disks were selected.

select_disks() {
    local disk_list=""
    local raid=false
    local zpool=false
    local raid_install=""
    local zpool_install=""
    local nitems
    local rv=1
    local item
    local raid_menu
    local zpool_menu
    local menu_item
    local output=/dev/null
    local opt

    while getopts "o:" opt; do
	case "${opt}" in
	    o)	output=${OPTARG} ;;
	    *)	echo "Usage: select_disks [-o output]" 1>&2 ; exit 1 ;;
	esac
    done
    shift $((OPTIND - 1 ))
    if [ $# -ne 0 ]; then
	echo "usage: select_disks [-o output]" 1>&2
	exit 1
    fi
    printf "" > ${output}

    nitems=0
    # First let's see if there are
    # any raid devices already set up.
    if find_raid_devices -o /tmp/raid-list
    then
	raid=true
	for item in $(cat /tmp/raid-list)
	do
	    nitems=$((nitems + 1))
	    get_disk_size -o /tmp/${item}.disksize raid/${item} 
	    raid_menu="${raid_menu} raid/${item} \"raid/${item} $(cat /tmp/${item}.disksize)\""
	done
    fi
    # Next let's check for any freenas-boot
    # zfs pools
    if find_zfs_pools -n freenas-boot -o /tmp/zpool-list
    then
	zpool=true
	for item in $(cat /tmp/zpool-list)
	do
	    nitems=$((nitems + 1))
	    zpool_menu="zfs/${item} 'Pool "${item}"'"
	done
    fi
    # Now let's see what disks we want to use
    # We have four possibilities:
    # 1:  zpool && raid
    # 2:  zpool && !raid
    # 3:  !zpool && raid
    # 4:  !zpool && !raid
    # The first one requires the user to
    # select the pool, a raid, or none.
    # The second one requires the user
    # to confirm.
    # The third requires the user to confirm,
    # and possibly select if there's more than
    # one raid.  (I don't think that's doable.)
    # The fourth one will be handled later.
    # 1-3 should set disklist to the disk(s)
    # that are involved.  raid_install should
    # be set to the name of the raid device
    # if that's chosen; zpool_install should
    # be set to the name of the pool.  (Which
    # has to be freenas-boot.)
    
    if ${zpool} && ${raid} ; then
	# We have both of these.
	# That makes things harder
	# By definition, nitems is at least two.
	if eval "dialog --title 'Select destination' \
		--menu 'Choose installation target.  If selected, RAID will be converted to ZFS; if selected, ZFS Pool will be destroyed.  (Configuration data will be stored if requested later)' \
		15 60 $((nitems + 1)) \
		${raid_menu} \
		${zpool_menu} \
		none 'Choose disks later (none of the above)'" \
	    2> /tmp/menu.item
	then
	    menu_item=$(cat /tmp/menu.item)
	    if [ "${menu_item}" = "none" ]; then
		disk_list=""
	    else
		disk_list=${menu_item}
	    fi
	fi
    elif ${zpool} ; then
	# Already have a pool.
	# Ask the user if we want to use this.
	# This should set disk_list if so.
	# Is it at all possible for nitems to be anything other
	# than 1, at this point?
	if [ ${nitems} -eq 1 ]; then
	    # Only one pool, so use a yesno dialog to see
	    # if we want to use it.
	    if eval "dialog --title 'Select destination' \
		--yesno \
		'Reuse freenas-boot (pool will be destroyed)' \
		5 60"
	    then
		disk_list=zfs/freenas-boot
	    fi
	else
	    if eval "dialog --title 'Choose destination' \
		--menu 'Select a pool (pool will be destroyed)' \
		10 60 $((nitems + 1)) \
		${zpool_menu} \
		none 'Choose  disks later (none of the above)'" \
		2> /tmp/menu.item
	    then
		menu_item=$(cat /tmp/menu.item)
		if [ ${menu_item} = "none" ]; then
		    disk_list=""
		else
		    disk_list=${menu_item}
		fi
	    fi
	fi
    elif ${raid} ; then
	# Have an Intel raid set up.
	# Ask the user if we want to use this.
	# This set disk_list if so.
	local raid_name
	if [ ${nitems} -eq 1 ]; then
	    # Only one raid, so use a yesno dialog to see
	    # if we want to use it.
	    raid_name=$(echo $raid_menu | awk ' { print $1; }')
	    if eval "dialog --title 'Select destination' \
		--yesno \
		'Reuse RAID '${raid_name}' (convert to ZFS)' \
		5 40"
	    then
		disk_list=${raid_name}
	    fi
	else
	    if eval "dialog --title 'Choose destination' \
		--menu 'Select a RAID set (will convert to ZFS)' \
		15 60 $((nitems + 1)) \
		${raid_menu} \
		none 'Choose  disks later (none of the above)'" \
		2> /tmp/menu.item
	    then
		menu_item=$(cat /tmp/menu.item)
		if [ ${menu_item} = "none" ]; then
		    disk_list=""
		else
		    disk_list=${menu_item}
		fi
	    fi
	fi
    fi

    if [ -z "${disk_list}" ]; then
	local disk_menu
	local _disk
	local _desc
	local _raid
	if [ -s /tmp/raid-list ]; then
	    _raid="-R /tmp/raid-list"
	fi
	if find_sata_doms ${_raid} -o /tmp/satadoms
	then
	    # Make these be the default.
	    # Or alternately just use them.
	    # Maybe only for truenas?
	    nitems=0
	    while read _disk _desc
	    do
		nitems=$((nitems + 1))
		disk_menu="${disk_menu} ${_disk} \"${_desc}\" on"
	    done < /tmp/satadoms
	    rm -f /tmp/satadoms
	fi
	find_disk_devices -o /dev/stdout | grep -v "${SATADOM}" > /tmp/disks.$$
	while read _disk _desc
	do
	    nitems=$((nitems + 1))
	    disk_menu="${disk_menu} ${_disk} \"${_desc}\" off"
	done < /tmp/disks.$$
	rm -f /tmp/disks.$$
	echo disk_menu: ${disk_menu}
	if eval "dialog --title 'Choose destination disk(s)' \
		--checklist 'Select at least one destination disk' \
		15 70 ${nitems} \
		${disk_menu} " \
	    2> /tmp/menu.item
	then
	    # We have disks selected!
	    disk_list=$(eval "echo $(cat /tmp/menu.item)")
	fi
	rm -f /tmp/menu.item
    fi

    if [ -z "${disk_list}" ]; then
	dialog --title "Choose destination media" \
	    --msgbox "No disks selected.  Install cancelled." 5 60
	return 1
    else
	rv=0
    fi
    if [ "${rv}" -eq 0 ]; then
	echo ${disk_list} > ${output}
    fi
    return ${rv}
}

#
# Given a set of disks, verify that they're
# usable.  If any of the disks is part of
# a raid or a zpool, ask if the user is
# sure about it.
# raid/* and zfs/* are skipped, as those
# were chosen explicitly.
# -l <file>	A list of raids and pools
#		to be destroyed due to these
#		disks.  The values are not
#		guaranteed to be unique.
#		Format is raid/<raid>
#		and zfs/<pool>.  E.g.
#		raid/r0 zfs/tank
# Arguments:  list of disks.
# Return value:
# 0	Disks are okay, or were approved.
# 1	Disks are not okay, or were rejected.

verify_selected_disks() {
    local disk_list
    local disk
    local rv=0
    local readonly raid_list="/tmp/raid-list"
    local readonly zfs_list="/tmp/pool-list"
    local warning_message
    local opt
    local listfile=/dev/null
    
    while getopts "l:" opt; do
	case "${opt}" in
	    l)	listfile=${OPTARG} ;;
	    *)	echo "Usage: verify_selectd_disk [-l file] disk [...]" 1>&2 ; exit 1;;
	esac
    done
    shift $((OPTIND - 1))

    if [ $# -eq 0 ]; then
	echo "usage: verify_selected_disks disk [...]" 1>&2
	exit 1
    fi
    # Now iterate through the disks

    find_raid_devices -o ${raid_list}
    find_zfs_pools -o ${zfs_list}

    printf "" > ${listfile}

    for disk
    do
	case ${disk} in
	    raid/*)
		echo "${disk}" >> ${listfile}
		continue ;;
	    zfs/*)
		echo "${disk}" >> ${listfile}
		continue ;;
	esac
	# Now we have to determine if disk is
	# part of a raid or zpool
	rm -f /tmp/name.$$
	if disk_is_raid_part -R ${raid_list} -O /tmp/name.$$ ${disk}
	then
	    warning_message="${warning_message}Disk ${disk} is part of raid $(cat /tmp/name.$$)\n"
	    echo raid/$(cat /tmp/name.$$) >> ${listfile}
	elif disk_in_pool -O /tmp/name.$$ ${disk}
	then
	    warning_message="${warning_message}Disk ${disk} is part of pool $(cat /tmp/name.$$)\n"
	    echo zfs/$(cat /tmp/name.$$) >> ${listfile}
	fi
    done
    if [ -n "${warning_message}" ]; then
	if dialog --title "Disk Conflict" \
	    --yes-label "Continue" \
	    --no-label "Cancel" \
	    --yesno \
	    "Continue will erase these drives, and destroy any pools \
or RAID sets to which they belong\n${warning_message}" \
	    15 40
	then
	    rv=0
	else
	    rv=1
	fi
    else
	rv=0
    fi
    return ${rv}
}

#
# Select a FreeNAS system to migrate from.
# Options:
# -o <file>	The device to migrate from.
#		This will be something like
#		ada0s1a, raid/r0s2a, or
#		freenas-boot/default
#		Note that it will have a "/"
#		in it only if it is a raid
#		or ZFS pool.
# Arguments:
# disk [...]	A list of disk devices (or zfs
#		pools) to search.
#
# Return values:
# 0 if one is selected (or there's only one choice)
# 1 if none is selected (interrupt or cancelled).
#
# If there is only one choice (i.e., only one device
# given, and it only has one FreeNAS OS to choose
# from), it won't ask the user to choose.  It will
# return 0, and store the device in the output file
# (if any).

select_migration_source() {
    local rv=1
    local opt
    local disk_list
    local disk
    local num_versions=0
    local output="/dev/null"
    local default_versions=""
    local menu_count=0
    local menu_items=""

    while getopts "o:" opt; do
	case "${opt}" in
	    o)	output=${OPTARG} ;;
	    *)	echo "Usage:  select_migration_source [-o output] disk [...]" 1>&2 ; exit 1;;
	esac
    done
    shift $((OPTIND - 1))
    if [ $# -eq 0 ]; then
	echo "usage:  select_migration_source [-o output] disk [...]" 1>&2
	exit 1
    fi

    rm -f /tmp/version.$$
    rm -f /tmp/all-versions.$$
    
    printf "" > ${output}

    for disk in "$@"
    do
	# See if there is a freenas install on the disk
	if find_freenas_versions -o /tmp/version.$$ ${disk}
	then
	    # /tmp/version.$$ has the list of versions.
	    # We'd like to get the default version, but
	    # i'm not sure how we represent that.
	    cat /tmp/version.$$ >> /tmp/all-versions.$$
	    default_versions="${default_versions} $(find_default_fs -o /dev/stdout ${disk})"
	fi
    done

    # Now /tmp/all-versions.$$ has all of the freenas versions
    # we found.  ${default_versions} has the default for each
    # disk we iterated over.
    # First, let's see if we only have one item
    num_versions=$(awk 'END { print NR; }' /tmp/all-versions.$$)

    if [ ${num_versions} -eq 0 ]
    then
	rv=0
    elif [ ${num_versions} -eq 1 ]
    then
	# That was easy.  There's only one choice.
	awk ' { print $2; }' /tmp/all-versions.$$ > ${output}
	rv=0
    else
	# We have multiple items, so let's construct
	# a menu list for it.
	while read type disk version timestamp
	do
	    menu_count=$((menu_count + 1))
	    menu_items="${disk} \"${version} $(date -r ${timestamp})\" ${menu_items}"
	done < /tmp/all-versions.$$
	eval "dialog --title 'Select Version' \
		--menu 'Choose version from which to migrate configuration data' \
		15 70 $((menu_count + 1)) \
		${menu_items} \
		none 'Do not migrate (clean install)'" \
	    2> /tmp/menu.item
	if [ $? -ne 0 -o "$(cat /tmp/menu.item)" = "none" ]; then
	    return 1
	else
	    cat /tmp/menu.item > ${output}
	    rm -f /tmp/menu.item
	    rv=0
	fi
    fi
    # Should not get here
    return ${rv}
}

#
# Start destroying raids and pools, and
# partitioning disks.
# Options:
# -l <file>	A list of the disks to be used.
# -R <file>	List of raids on the system.
# -Z <file>	A list of zpools on the system.
# Arguments:
# disk [...]
#
# disk is expected to be either:
# raid/<raid_name> (e.g., raid/r0)
# zfs/<pool_name> (e.g., zfs/freenas-boot)
# <device_name> (e.g., ada0)
# Because of raid and zfs pools, the list of disks
# may not be the same as the install media.
# In order to work, this requires that find_raid_devices
# and find_zfs_pools have run, so that the *.subdisks
# files are around.
#
# This is just a helper function to make it easier to read.
partition_disk() {
    local disk

    disk=$1

    set -e

    gpart destroy -F ${disk} > /dev/null 2>&1 || true
    # Get rid of any MBR.  This shouldn't be necessary,
    # but there were some problems possibly caused by caching.
    dd if=/dev/zero of=/dev/${disk} bs=1m count=1 > /dev/null
    # Create a GPT partition
    gpart create -s gpt ${disk} > /dev/null
    # For grub
    gpart add -t bios-boot -i 1 -s 512k ${disk} > /dev/null
    # Should we do something special for truenas?
    if is_truenas; then
	# This does assume the disk is larger than 16g.
	# We should check that.
	gpart add -t freebsd-swap -i 3 -s 16g ${disk}
    fi
    # Now give the rest of the disk to freenas-boot
    gpart add -t freebsd-zfs -i 2 -a 4k ${disk} > /dev/null
    # Now we make it active, for legacy support.
    gpart set -a active ${disk}
    set +e
    return 0
}

prepare_disks() {
    local output="/dev/null"
    local opt
    local disk
    local pool
    local raid
    local disk_list
    local raid_list=/dev/null
    local pool_list=/dev/null

    while getopts "l:R:Z:" opt; do
	case "${opt}" in
	    l)	output="${OPTARG}" ;;
	    R)	raid_list="${OPTARG}" ;;
	    Z)	pool_list="${OPTARG}" ;;
	    *)	echo "Usage: prepare_disks [-l disk_list] disk [...]" 1>&2 ; exit 1 ;;
	esac
    done
    shift $((OPTIND - 1 ))
    if [ $# -eq 0 ]; then
	echo "usage: prepare_disks [-l disk_list] disk [... ]" 1>&2
	exit 1
    fi

    for disk
    do
	if pool=$(expr "${disk}" : "^zfs/\(.*\)")
	then
	    # need to get the disks for ${pool}
	    # With zpools, we'll just repartition the
	    # disks.
	    disk_list="$(cat /tmp/pool-${pool}.subdisks) ${disk_list}"
	elif raid=$(expr "${disk}" : "^raid/\(r[0-9]*\)")
	then
	    # Need to get the disks for ${raid}
	    disk_list="$(cat /tmp/raid-${raid}.subdisks) ${disk_list}"
	    graid delete ${disk}
	elif [ -c /dev/${disk} ]
	then
	    # Let's see if it is part of a raid.
	    if [ -f ${raid_list} ]; then
		if disk_is_raid_part -R ${raid_list} -o /tmp/raid_name.$$
		then
		    graid remove $(cat /tmp/raid_name.$$) ${disk} || true
		fi
		rm -f /tmp/raid_name.$$
	    fi
	    # If it's a zpool member, we'll just
	    # go with repartitioning it.  Nothing can go wrong with
	    # that plan, right?
	    disk_list="${disk} ${disk_list}"
	else
	    echo "Unknown device type ${disk}" 1>&2
	    exit 1
	fi
>>>>>>> Much to my surprise, that worked.  At least for a fresh install.
    done
    # Now ${disk_list} has all the disks we need to partition
    for disk in ${disk_list}
    do
	if ! partition_disk ${disk}; then
	    return 1
	fi
    done
    # We only get here if we've successfully partitioned all the drives.
    echo ${disk_list} >> ${output}
    return 0
}

#
# Format the disks.
# This assumes each disk has been partitioned already, in
# prepare_disk
# All this does is create a pool out of all of the disks,
# and then creates two datasets on it.
format_disks() {
    local _mirror=""
    local disk_list
    local disk

    if [ $# -eq 0 ]; then
	echo "Usage:  format_disks disk [...]" 1>&2
	return 1
    fi
    set -e
    if [ $# -gt 1 ]; then
	_mirror="mirror"
    fi
    for disk
    do
	disk_list="${disk}p2 ${disk_list}"
    done
    zpool create -f -o cachefile=/tmp/zpool.cache -o version=28 \
	-O mountpoint=none -O atime=off -O canmount=off \
	freenas-boot ${_mirror} ${disk_list}
    zfs create -o canmount=off freenas-boot/ROOT
    zfs create -o mountpoint=legacy freenas-boot/ROOT/default
    zfs create -o mountpoint=legacy freenas-boot/grub
    set +e
    return 0
}

#
# Prompt for a password.  This is
# only used on non-upgrade installs.
# Option:
# -o file	File to contain the password
# Return values:
# 0	password was entered
# 1	no password
prompt_password() {
    local opt
    local outfile=/dev/null
    local values value password="" password1 password2 _counter _tmpfile="/tmp/pwd.$$"

    cat << __EOF__ > /tmp/dialogconf
bindkey formfield TAB FORM_NEXT
bindkey formfield DOWN FORM_NEXT
bindkey formfield UP FORM_PREV
bindkey formbox DOWN FORM_NEXT
bindkey formbox TAB FORM_NEXT
bindkey formbox UP FORM_PREV
__EOF__

    while getopts "o:" opt
    do
	case "${opt}" in
	    o)	outfile=${OPTARG};;
	    *)	echo "Usage: prompt_password [-o file]" 1>&2 ; return 1;;
	esac
    done
    shift $((OPTIND - 1))
    if [ $# -ne 0 ]; then
	echo "usage: prompt_password [-o file]" 1>&2
	return 1
    fi

    while true; do
	env DIALOGRC="/tmp/dialogconf" dialog --insecure \
	    --output-fd 3 \
	    --visit-items \
	    --passwordform "Enter your root password; cancel for no root password" \
	    10 50 0 \
	    "Password:" 1 1 "" 0 20 25 20 \
	    "Confirm Password:" 2 1 "" 2 20 25 20 \
	    3> ${_tmpfile}

	if [ $? -ne 0 ]; then
	    rm -f ${_tmpfile}
	    return 1
	fi

	{ read password1 ; read password2; } < ${_tmpfile}
	rm -f ${_tmpfile}

	if [ "${password1}" != "${password2}" ]; then
	    dialog --msgbox "Passwords do not match." 7 60 2> /dev/null
	elif [ -z "${password1}" ]; then
	    dialog --msgbox "Empty password is not secure" 7 60 2> /dev/null
	else
	    password="${password1}"
	    break
	fi

    done

    rm -f ${DIALOGRC}
    echo -n "${password}" > ${outfile}
    return 0
}

#
# Install grub into the specified mountpoint.
# No options; must be at least two arguments:
# mountpoint, and disk.  Multiple disks can
# be specified.
install_grub() {
	local _disk _disks
	local _mnt

	if [ $# -lt 2 ]; then
	    echo "Usage: install_grub <mntpoint> disk [...]" 1>&2
	    return 1
	fi
	_mnt="$1"
	shift

	# Install grub
	chroot ${_mnt} /sbin/zpool set cachefile=/boot/zfs/rpool.cache freenas-boot
	chroot ${_mnt} /etc/rc.d/ldconfig start
	/usr/bin/sed -i.bak -e 's,^ROOTFS=.*$,ROOTFS=freenas-boot/ROOT/default,g' ${_mnt}/usr/local/sbin/beadm ${_mnt}/usr/local/etc/grub.d/10_ktrueos
	# Having 10_ktruos.bak in place causes grub-mkconfig to
	# create two boot menu items.  So let's move it out of place
	mkdir -p /tmp/bakup
	mv ${_mnt}/usr/local/etc/grub.d/10_ktrueos.bak /tmp/bakup
	for _disk
	do
	    chroot ${_mnt} /usr/local/sbin/grub-install --modules='zfs part_gpt' /dev/${_disk}
	done
	chroot ${_mnt} /usr/local/sbin/beadm activate default
	chroot ${_mnt} /usr/local/sbin/grub-mkconfig -o /boot/grub/grub.cfg > /dev/null 2>&1
	# And now move the backup files back in place
	mv ${_mnt}/usr/local/sbin/beadm.bak ${_mnt}/usr/local/sbin/beadm
	mv /tmp/bakup/10_ktrueos.bak ${_mnt}/usr/local/etc/grub.d/10_ktrueos
	return 0
}

#
# Do the install.
# Options:
# -N	Non-interactive.
# Arguments:
# disk [...]	A list of disks to install on.
#		This may be a raid disk (e.g., raid/r0),
#		or a pool (e.g, freenas-boot), or just
#		a disk (e.g., ada0).  Multiple may be
#		specified.
menu_install() {
    local install_media
    local interactive=true
    local opt
    local rv=1
    local upgrade=false
    local readonly config_backup="/tmp/config-backup"
    local readonly raid_list="/tmp/raid-list"
    local readonly pool_list="/tmp/pool-list"
    local readonly deadpool="/tmp/deadpool"
    local readonly migrate="/tmp/migrate"
    local readonly mountpoint="/tmp/install_mount"
    local readonly CD_UPGRADE_SENTINEL="/data/cd-upgrade"
    local readonly NEED_UPDATE_SENTINEL="/data/need-update"
    local readonly POOL="freenas-boot"
    local OS
    local real_disks
    local password

    if is_truenas; then
	OS=TrueNAS
    else
	OS=FreeNAS
    fi
    # First, let's clean up some known files
    rm -rf ${config_backup}
    rm -f ${raid_list}
    rm -f ${pool_list}
    rm -f ${deadpool}
    rm -f ${migrate}

    while getopts "N" opt; do
	case "${opt}" in
	    N)	interactive=false ;;
	    *)	echo "Usage: menu_install [-N] [disk [...]]" 1>&2 ; exit 1;;
	esac
    done
    shift $((OPTIND - 1))

    rm -f /tmp/deadpool
    rm -f /tmp/migrate

    if ! ${interactive} && [ $# -eq 0 ]; then
	echo "Cannot be non-interactive unless installation media is given" 1>&2
	return 1
    fi

    if [ $# -gt 0 ]; then
	install_media="$@"
    else
	if ! select_disks -o /tmp/install-media.$$
	then
	    echo "Need dialog box here, no installation media selected"
	    return 1
	else
	    install_media=$(cat /tmp/install-media.$$)
	    rm -f /tmp/install-media.$$
	fi
    fi
    if ${interactive}; then
	if ! verify_selected_disks -l ${deadpool} ${install_media}
	then
	    echo "Need some dialog here:  disk list not approved"
	    return 1
	fi
    fi
    # At this point, ${install_media} has the list of devices on
    # which to install, and /tmp/deadpool has a list of pools and raid
    # devces we have to do bad things to.
    # Note one deficiency here:  if you have a raid device (e.g., raid/r0),
    # and you do not select it -- but then you select the component disks
    # for it, find_freenas_versions will not work.  (Because, with the
    # intel raid controller, raid/r0s1a will exist, but ada0s1 a will not.)
    # To fix this, find_freenas_versions would need to see if each disk
    # is part of a raid, and if so, use that.
    if find_freenas_versions ${install_media}; then
	upgrade=true
	if ${interactive}; then
	    if ! dialog --title "Perform upgrade" \
		--yesno \
		"Perform upgrade\n(No means perform clean install)" \
		8 40
	    then
		upgrade=false
	    fi
	fi
    fi
    if ${upgrade}; then
	if ${interactive}; then
	    if ! select_migration_source -o ${migrate} ${install_media}
	    then
		echo "Need dialog here:  upgrade was selected, but cancelled"
		return 1
	    fi
	else
	    # Non-interactive can only work with one device, so we'll
	    # rely on that
	    if ! find_default_fs -o ${migrate} ${install_media}
	    then
		echo "Need to log failure here"
		return 1
	    fi
	fi
    fi
    # At this point:
    # ${install_media} has the list of devices we want to install on.
    # ${upgrade} is either true or false.
    # /tmp/migrate has the media to migrate from if ${upgrade} is true.
    # For each raid and pool in ${install_media}, we have
    # /tmp/raid-<x>.subdisks, and /tmp/pool-<x>.subdisks.
    
    if ${interactive}; then
	local migrate_text
	local pool_text
	if [ -s ${migrate} ]; then
	    migrate_text="Configuration information will be migrated from $(cat ${migrate})"
	fi
	if [ -s ${deadpool} ]; then
	    pool_text="The following pools / RAIDs will be destroyed:\n$(sed -e 's#^zfs/##' ${deadpool})\n"
	fi
	dialog --title "Last chance" \
	    --yesno "Are you sure you are ready to install?\n
${pool_text}\n
${migrate_text}" \
	15 60
	if [ $? -ne 0 ]; then
	    dialog --title "Installation cancelled" \
		--msgbox "Installation has been cancelled" \
		5 20
	    return 1
	fi
    fi
    if ${upgrade}; then
	mkdir -p ${config_backup}
	if ! save_freenas_config -d ${config_backup} $(cat ${migrate})
	then
	    if ${interactive} && dialog --title "Migration failed" \
		--yes-label Continue \
		--no-label Cancel \
		--yesno "Migration of configuration data failed; continue?"
	    then
		upgrade=false
		rm -rf ${config_backup}
	    else
		return 1
	    fi
	fi
    elif ${interactive}; then
	if prompt_password -o /tmp/passwd.$$; then
	    password="$(cat /tmp/passwd.$$)"
	fi
	rm -f /tmp/passwd.$$
    fi

    # At this point, we have install_media telling us where
    # to install.  (This will be a list of disks; pools that
    # we use entirely will be zfs/<pool_name>; raids will be
    # raid/<raid_name>.)
    # /tmp/migrate has the name of the device to migrate from.
    # (Well, moot by this point, save_freenas_config above
    # saved it, and it's in /tmp/config-backup.)
    # /tmp/deadpool has a list of raids and pools we need
    # to destroy.  As with install_media, we have marked
    # pools as zfs/<pool_name>, raids as raid/<raid_name>.
    # /tmp will also have pool-<pool_name>.subdisks, and
    # raid-<raid_name>.subdisks.
    # Note that deadpool is not the same as install_media;
    # it's just a list of raids and pools we need to remove
    # media from.
    # For raids, we can remove the disks mentioned in
    # install_media; if there are no more disks in it, the
    # raid is destroyed.
    # For zfs pools, however, we're in a harder spot:  we
    # can try removing them (using zpool detach), or we
    # could just take the drives, and repartition them.
    # Or we could destroy the pool.  To get to this point,
    # the user has had to accept the disks multiple times,
    # and been told that it will impact the pool it is in.
    # Note that we only care about this for disks in install_media;
    # for pools in install_media, we can simply reformat the disks
    # and remake the pool.
    # First we need to have the raid and pool lists
    if [ ! -f ${raid_list} ]; then
	find_raid_devices -o ${raid_list}
    fi
    if [ ! -f ${pool_list} ]; then
	find_zfs_pools -o ${pool_list}
    fi

    if ! prepare_disks -R ${raid_list} -Z ${pool_list} -l /tmp/disks.$$ ${install_media}
    then
	if ${interactive}; then
	    dialog --title "Installation failed" \
		--msgbox "Disk preparation failed" \
		5 30
	fi
	return 1
    fi
    real_disks=$(cat /tmp/disks.$$)
    rm -f /tmp/disks.$$
    if ! format_disks ${real_disks}
    then
	if ${interactive}; then
	    dialog --title "Installation failed" \
		--msgbox "Volume formatting failed" \
		5 30
	fi
	return 1
    fi

    # The filesystems have been created.
    # So mount them
    mkdir -p ${mountpoint}
    if mount -t zfs -o noatime ${POOL}/ROOT/default ${mountpoint}
    then
	mkdir -p ${mountpoint}/boot/grub
	if mount -t zfs -o noatime ${POOL}/grub ${mountpoint}/boot/grub
	then
	    # Both filesystems mounted
	    # Prepare the install!
	    # First, restore the config data
	    if ${upgrade}; then
		restore_freenas_config ${config_backup} ${mountpoint}
		: > ${mountpoint}/${CD_UPGRADE_SENTINEL}
		: > ${mountpoint}/${NEED_UPDATE_SENTINEL}
	    else
		mkdir -p ${mountpoint}/data
		set -x
		mkdir -p ${mountpoint}/data
		test -d ${mountpoint}/data || read -p "What happened?" foo
		cp -R /data/* ${mountpoint}/data
		chown -R www:www ${mountpoint}/data
	    fi
	    if /usr/local/bin/freenas-install -P /.mount/${OS}/Packages \
		-M /.mount/${OS}-MANIFEST \
		${mountpoint}
	    then
		rm -f ${mountpoint}/conf/default/etc/fstab ${mountpoint}/data/conf/base/etc/fstab
		echo "${POOL}/grub	/boot/grub	zfs	rw,noatime	1	0" > ${mountpoint}/etc/fstab
		if is_truenas; then
		    for disk in ${real_disks}; do
			echo "/dev/${disk}p3.eli	none	swap	sw	0 0" >> ${mountpoint}/data/fstab.swap
		    done
		fi
		ln ${mountpoint}/etc/fstab ${mountpoint}/conf/base/etc/fstab || echo "Cannot link fstab"
		# Now we need to set up booting
		mount -t devfs devfs ${mountpoint}/dev
		mount -t tmpfs tmpfs ${mountpoint}/var
		chroot ${mountpoint} /usr/sbin/mtree -deUf /etc/mtree/BSD.var.dist -p /var
		zpool set bootfs=${POOL}/ROOT/default ${POOL}
		if ! install_grub ${mountpoint} ${real_disks}; then
		    echo "Dialog about failure to install grub"
		    return 1
		fi
		if [ -n "${password}" ]; then
		    chroot ${mountpoint} /etc/netcli reset_root_pw "${password}"
		fi
		umount ${mountpoint}/dev
		umount ${mountpoint}/var
	    fi
	    umount ${mountpoint}/boot/grub
	else
	    if ${interactive}; then
		echo "dialog about failure to mount grub"
	    fi
	    return 1
	fi
	umount ${mountpoint}
	zpool export ${POOL}
    else
	if ${interactive}; then
	    echo "dialog about failure to mount freenas-boot"
	fi
	return 1
    fi
    echo "Install media = ${install_media}"
    test -f ${migrate} && echo "Migrate from $(cat ${migrate})"
    test -f ${deadpool} && echo "Dead pools $(cat ${deadpool})"
    echo "Disks to kill are ${real_disks}"

    return ${rv}

}

menu_shell()
{
    /bin/sh
}

menu_reboot()
{
    echo "Rebooting..."
    reboot >/dev/null
}

menu_shutdown()
{
    echo "Halting and powering down..."
    halt -p >/dev/null
}

#
# Use the following kernel environment variables
#
#  test.nfs_mount -  The NFS directory to mount to get
#                    access to the test script.
#  test.script    -  The path of the test script to run,
#                    relative to the NFS mount directory.
#  test.run_tests_on_boot - If set to 'yes', then run the
#                           tests on bootup, before displaying
#                           the install menu. 
#
#  For example, if the following variables are defined:
#
#    test.nfs_mount=10.5.0.24:/usr/jails/pxeserver/tests
#    test.script=/tests/run_tests.sh
#
#  Then the system will execute the following:
#     mount -t nfs 10.5.0.24:/usr/jails/pxeserver/tests /tmp/tests
#     /tmp/tests/tests/run_tests.sh
menu_test()
{
    local _script
    local _nfs_mount

    _script="$(kenv test.script 2> /dev/null)"
    _nfs_mount="$(kenv test.nfs_mount 2> /dev/null)"
    if [ -z "$_script" -o -z "$_nfs_mount"  ]; then
        return
    fi
  
    if [ -e /tmp/tests ]; then
        umount /tmp/tests 2> /dev/null
        rm -fr /tmp/tests
    fi 
    mkdir -p /tmp/tests
    if [ ! -d /tmp/tests ]; then
        echo "No test directory"
        wait_keypress
    fi
    umount /tmp/tests 2> /dev/null
    mount -t nfs -o ro "$_nfs_mount" /tmp/tests
    if [ ! -e "/tmp/tests/$_script" ]; then
        echo "Cannot find /tmp/tests/$_script"
        wait_keypress
        return
    fi

    dialog --stdout --prgbox /tmp/tests/$_script 15 80
}

main()
{
    local _tmpfile="/tmp/answer"
    local _number
    local _test_option=

    if [ $# -ne 0 ]; then
	# Argument(s) will have device name(s)
	menu_install -N "$@"
	exit $?
    fi

    case "$(kenv test.run_tests_on_boot 2> /dev/null)" in
    [Yy][Ee][Ss])
        menu_test
        ;;
    esac

    if [ -n "$(kenv test.script 2> /dev/null)" ]; then
        _test_option="5 Test"
    fi

    while :; do

        dialog --clear --title "$AVATAR_PROJECT $AVATAR_VERSION Console Setup" --menu "" 12 73 6 \
            "1" "Install/Upgrade" \
            "2" "Shell" \
            "3" "Reboot System" \
            "4" "Shutdown System" \
            $_test_option \
            2> "${_tmpfile}"
        _number=$(cat "${_tmpfile}")
        case "${_number}" in
            1) menu_install ;;
            2) menu_shell ;;
            3) menu_reboot ;;
            4) menu_shutdown ;;
            5) menu_test ;;
        esac
    done
}

if is_truenas ; then
    . "$(dirname "$0")/install_sata_dom.sh"
fi

main "$@"
