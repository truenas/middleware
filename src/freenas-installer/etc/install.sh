#!/bin/sh

# vim: noexpandtab ts=8 sw=4 softtabstop=4

# Setup a semi-sane environment
PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin:/rescue
export PATH
HOME=/root
export HOME
TERM=${TERM:-xterm}
export TERM

. /etc/avatar.conf

# Boot Pool
BOOT_POOL="boot-pool"
NEW_BOOT_POOL="boot-pool"

# Constants for base 10 and base 2 units
: ${kB:=$((1000))}      ${kiB:=$((1024))};       readonly kB kiB
: ${MB:=$((1000 * kB))} ${MiB:=$((1024 * kiB))}; readonly MB MiB
: ${GB:=$((1000 * MB))} ${GiB:=$((1024 * MiB))}; readonly GB GiB
: ${TB:=$((1000 * GB))} ${TiB:=$((1024 * GiB))}; readonly TB TiB

is_truenas()
{
	dmidecode -s system-product-name | grep -i "truenas" | grep -qv MINI
	return $?
}

# Constant media size threshold for allowing swap partitions.
: ${MIN_SWAPSAFE_MEDIASIZE:=$((60 * GB))}; readonly MIN_SWAPSAFE_MEDIASIZE

# Check if it is safe to create swap partitions on the given disks.
#
# The result can be forced by setting SWAP_IS_SAFE in the environment to either
# "YES" or "NO".
#
# Sets SWAP_IS_SAFE to "YES" if
#   we are on TrueNAS
#   *or*
#   every disk in $@ is >= ${MIN_SWAPSAFE_MEDIASIZE} and none is USB and user says ok
# Otherwise sets SWAP_IS_SAFE to "NO".
#
# Use `is_swap_safe` to check the value of ${SWAP_IS_SAFE}.
check_is_swap_safe()
{
    # We assume swap is safe on TrueNAS,
    # and we try to use the existing value for ${SWAP_IS_SAFE} if already set.
    if ! is_truenas && [ -z "${SWAP_IS_SAFE}" ] ; then
	local _disk
	# Check every disk in $@, aborting if an unsafe disk is found.
	for _disk ; do
	    if [ $(diskinfo "${_disk}" | cut -f 3) -lt ${MIN_SWAPSAFE_MEDIASIZE} ] ||
		camcontrol negotiate "${_disk}" -v | grep -qF 'umass-sim' ; then
		SWAP_IS_SAFE="NO"
		break
	    fi
	done
    fi
    # Make sure we have a valid value for ${SWAP_IS_SAFE}.
    # If unset, we are either on TrueNAS or didn't find an unsafe disk.
    case "${SWAP_IS_SAFE:="YES"}" in
	# Accept YES or NO (case-insensitive).
	[Yy][Ee][Ss])
	    # Confirm swap setup
	    if ! is_truenas &&
		! dialog --clear --title "${AVATAR_PROJECT}" \
		    --yes-label "Create swap" --no-label "No swap" --yesno  \
		    "Create 16GB swap partition on boot devices?" \
		    7 74 ; then
		SWAP_IS_SAFE="NO"
	    fi
	    ;;
	[Nn][Oo]) ;;
	# Reject other values.
	*)  echo "Ignoring invalid value for SWAP_IS_SAFE: ${SWAP_IS_SAFE}"
	    unset SWAP_IS_SAFE
	    check_is_swap_safe "$@"
	    ;;
    esac
    export SWAP_IS_SAFE
}

# A specialized checkyesno for SWAP_IS_SAFE.
# Returns 0 if it is ok to set up swap on the chosen disks, otherwise 1.
# `check_is_swap_safe` must be called once before calling `is_swap_safe`.
is_swap_safe()
{
    case "${SWAP_IS_SAFE:?}" in
	[Yy][Ee][Ss]) true;;
	*) false;;
    esac
}

get_product_path()
{
    echo /cdrom /.mount
}

get_image_name()
{
    find $(get_product_path) -name "$AVATAR_PROJECT-$AVATAR_ARCH.img.xz" -type f
}

# The old pre-install checks did several things
# 1:  Don't allow going from FreeNAS to TrueNAS or vice versa
# 2:  Don't allow downgrading.  (Not sure we can do that now.)
# 3:  Check memory size and cpu speed.
# This does memory size only for now.
pre_install_check()
{
    # We need at least 8 GB of RAM
    # minus 1 GB to allow for reserved memory
    local minmem=$((7 * GiB))
    local memsize=$(sysctl -n hw.physmem)

    if [ ${memsize} -lt ${minmem} ]; then
	dialog --clear --title "${AVATAR_PROJECT}" --defaultno \
	--yesno "This computer has less than the recommended 8 GB of RAM.\n\nOperation without enough RAM is not recommended.  Continue anyway?" 7 74 || return 1
    fi
    return 0
}

# Convert /etc/version* to /etc/avatar.conf
#
# 1 - old /etc/version* file
# 2 - dist version of avatar.conf
# 3 - destination avatar.conf
upgrade_version_to_avatar_conf()
{
    local destconf srcconf srcversion
    local project version revision arch

    srcversion=$1
    srcconf=$2
    destconf=$3

    set -- $(sed -E -e 's/-amd64/-x64/' -e 's/-i386/-x86/' -e 's/(.*)-([^-]+) \((.*)\)/\1-\3-\2/' -e 's/-/ /' -e 's/-([^-]+)$/ \1/' -e 's/-([^-]+)$/ \1/' < $srcversion)

    project=$1
    version=$2
    revision=$3
    arch=$4

    sed \
        -e "s,^AVATAR_ARCH=\".*\",AVATAR_ARCH=\"$arch\",g" \
        -e "s,^AVATAR_BUILD_NUMBER=\".*\"\$,AVATAR_BUILD_NUMBER=\"$revision\",g" \
        -e "s,^AVATAR_PROJECT=\".*\"\$,AVATAR_PROJECT=\"$project\",g" \
        -e "s,^AVATAR_VERSION=\".*\"\$,AVATAR_VERSION=\"$version\",g" \
        < $srcconf > $destconf.$$

    mv $destconf.$$ $destconf
}

wait_keypress()
{
    local _tmp
    read -p "Press ENTER to continue." _tmp
}

sort_disklist()
{
    sed 's/\([^0-9]*\)/\1 /' | sort +0 -1 +1n | tr -d ' '
}

# return 0 if no raid devices, or !0 if there are some.
get_raid_present()
{
	local _cnt
	local _dummy

	if [ ! -d "/dev/raid" ] ; then
		return 0;
	fi

	_cnt=0
	ls /dev/raid/ > /tmp/raidfiles
	while read _dummy ; do _cnt=$(($_cnt + 1));done < /tmp/raidfiles
	return $_cnt
}

get_physical_disks_list()
{
    local _boot=$(glabel status | awk '/iso9660\/(FREE|TRUE)NAS/ { print $3 }')
    local _disk

    VAL=""
    for _disk in $(sysctl -n kern.disks)
    do
	if [ "${_disk}" = "${_boot}" ]; then
	    continue
	fi
	VAL="${VAL} ${_disk}"
    done

    get_raid_present
    if [ $? -ne 0 ] ; then
	VAL="$VAL `cd /dev ; ls -d raid/* | grep -v '[0-9][a-z]'`"
    fi

    VAL=`echo $VAL | tr ' ' '\n'| grep -v '^cd' | sort_disklist`
    export VAL
}

get_media_description()
{
    local _media
    local _description
    local _cap

    _media=$1
    if [ -n "${_media}" ]; then
	_description=`geom disk list ${_media} 2>/dev/null \
	    | sed -ne 's/^   descr: *//p'`
	if [ -z "${_description}" ]; then
	    _description="Unknown Device"
	fi
	_cap=`diskinfo ${_media} | awk \
	    -v TiB=${TiB}.0 \
	    -v GiB=${GiB}.0 \
	    -v MiB=${MiB}.0 \
	'{
	    capacity = int($3);
	    if (capacity >= TiB) {
	        printf("%.1f TiB", capacity / TiB);
	    } else if (capacity >= GiB) {
	        printf("%.1f GiB", capacity / GiB);
	    } else if (capacity >= MiB) {
	        printf("%.1f MiB", capacity / MiB);
	    } else {
	        printf("%d Bytes", capacity);
	    }
	}'`
	echo "${_description} -- ${_cap}"
    fi
}

disk_is_mounted()
{
    local _dev

    for _dev
    do
	if mount -v | grep -qE "^/dev/${_dev}[sp][0-9]+"
	then
	    return 0
	fi
    done
    return 1
}

new_install_verify()
{
    local _type="$1"
    shift
    local _upgradetype="$1"
    shift

    local _disks="$*"
    local _tmpfile="/tmp/msg"
    cat << EOD > "${_tmpfile}"
WARNING:
EOD

    if [ "$_upgradetype" = "inplace" ] ; then
      echo "- This will install into existing zpool on ${_disks}." >> ${_tmpfile}
    else
      echo "- This will erase ALL partitions and data on ${_disks}." >> ${_tmpfile}
    fi

    cat << EOD >> "${_tmpfile}"
- You can't use ${_disks} for sharing data.

NOTE:
- Installing on SATA, SAS, or NVMe flash media is recommended.
  USB flash sticks are discouraged.

Proceed with the ${_type}?
EOD
    _msg=`cat "${_tmpfile}"`
    rm -f "${_tmpfile}"
    dialog --clear --title "$AVATAR_PROJECT ${_type}" --yesno "${_msg}" 13 74
    [ $? -eq 0 ] || abort
}

ask_upgrade()
{
    local _disk="$1"
    local _tmpfile="/tmp/msg"
    cat << EOD > "${_tmpfile}"
Upgrading the installation will preserve your existing configuration.

Do you wish to perform an upgrade or a fresh installation on ${_disk}?
EOD
    _msg=`cat "${_tmpfile}"`
    rm -f "${_tmpfile}"
    dialog --title "Upgrade this $AVATAR_PROJECT installation" --no-label "Fresh Install" --yes-label "Upgrade Install" --yesno "${_msg}" 8 74
    return $?
}

ask_upgrade_inplace()
{
    local _tmpfile="/tmp/msg"
    cat << EOD > "${_tmpfile}"
User configuration settings and storage volumes are preserved and not affected by this step.\n\n
The boot device can be formatted to remove old versions, or the upgrade can be installed in a new boot environment without affecting any existing versions.
EOD
    _msg=`cat "${_tmpfile}"`
    rm -f "${_tmpfile}"
    dialog --trim --title "Update Method Selection" --yes-label "Install in new boot environment" --no-label "Format the boot device" --yesno "${_msg}" 0 0
    return $?
}

ask_boot_method()
{
    # If we are not on efi, set BIOS as the default selected option
    dlgflags=""
    if [ "$BOOTMODE" != "UEFI" ] ; then
      dlgflags="--defaultno"
    fi

    local _tmpfile="/tmp/msg"
    cat << EOD > "${_tmpfile}"
$AVATAR_PROJECT can be booted in either BIOS or UEFI mode.

BIOS mode is recommended for legacy and enterprise hardware,
whereas UEFI may be required for newer consumer motherboards.
EOD
    _msg=`cat "${_tmpfile}"`
    rm -f "${_tmpfile}"
    dialog ${dlgflags} --title "$AVATAR_PROJECT Boot Mode" --no-label "Boot via BIOS" --yes-label "Boot via UEFI" --yesno "${_msg}" 8 74
    return $?
}

install_loader()
{
    local _disk _disks
    local _mnt

    _mnt="$1"
    shift
    _disks="$*"

    # When doing inplace upgrades, its entirely possible we've
    # booted in the wrong mode (I.E. bios/efi)
    # Default to re-stamping what was already used on the current install
    _boottype="$BOOTMODE"
    if [ "${_upgrade_type}" = "inplace" ] ; then
      if gpart show ${_disks} | grep -qF 'efi' ; then
         _boottype="UEFI"
      else
         _boottype="BIOS"
      fi
    fi

    for _disk in $_disks
    do
	if [ "$_boottype" = "UEFI" ] ; then
	    echo "Stamping EFI loader on: ${_disk}"
	    mkdir -p /tmp/efi
	    mount -t msdosfs /dev/${_disk}p1 /tmp/efi
	    # Copy the .efi file and create a fallback startup script
	    mkdir -p /tmp/efi/efi/boot
	    cp ${_mnt}/boot/boot1.efi /tmp/efi/efi/boot/BOOTx64.efi
	    echo "BOOTx64.efi" > /tmp/efi/efi/boot/startup.nsh
	    umount /tmp/efi
	else
	    echo "Stamping GPT loader on: ${_disk}"
	    gpart modify -i 1 -t freebsd-boot ${_disk}
	    chroot ${_mnt} gpart bootcode -b /boot/pmbr -p /boot/gptzfsboot -i 1 /dev/${_disk}
	fi
    done

    return 0
}

nasdb()
{
    local mnt=$1
    local query=$2

    chroot "${mnt}" /usr/local/bin/sqlite3 /data/freenas-v1.db "${query}"
}

videoconsole()
{
    if [ "$BOOTMODE" = "UEFI" ]; then
	echo efi
    else
	echo vidconsole
    fi
}

mseries()
{
    dmidecode -s system-product-name | grep -iv "MINI" | grep -iq "TRUENAS-M"
}

save_serial_settings()
{
    local mnt="$1"

    local RB_SERIAL=0x1000
    local RB_MULTIPLE=0x20000000

    local VIDEO_ONLY=0
    local SERIAL_ONLY=$((RB_SERIAL))
    local VID_SER_BOTH=$((RB_MULTIPLE))
    local SER_VID_BOTH=$((RB_SERIAL | RB_MULTIPLE))
    local CON_MASK=$((RB_SERIAL | RB_MULTIPLE))

    local boothowto=$(sysctl -n debug.boothowto)
    case $((boothowto & CON_MASK)) in
    $VIDEO_ONLY|$VID_SER_BOTH)
	# Do nothing if we booted with video as the primary console.
	return 0
	;;
    $SERIAL_ONLY)
	local console="comconsole"
	;;
    $SER_VID_BOTH)
	# we skip setting only comconsole on UEFI booted mseries devices
	# since doing so prevents the bsd boot loader screen from showing
	# on the iKVM/HTML5 IPMI website.
	if [ "$(kenv console)" = "comconsole" ] && ! mseries; then
	    # We used the serial boot menu entry and efi has a serial port.
	    # Enable only comconsole so loader output is not duplicated.
	    local console="comconsole"
	else
	    local console="comconsole,$(videoconsole)"
	fi
	;;
    esac

    local port=$(kenv hw.uart.console | sed -En 's/.*io:([0-9a-fx]+).*/\1/p')
    if [ -n "${port}" ] ; then
	echo "comconsole_port=\"${port}\"" >> ${mnt}/boot/loader.conf.local
	nasdb ${mnt} "update system_advanced set adv_serialport = '${port}'"
    fi

    local speed=$(kenv hw.uart.console | sed -En 's/.*br:([0-9]+).*/\1/p')
    if [ -n "${speed}" ] ; then
	echo "comconsole_speed=\"${speed}\"" >> ${mnt}/boot/loader.conf.local
	nasdb ${mnt} "update system_advanced set adv_serialspeed = ${speed}"
    fi

    cat >> ${mnt}/boot/loader.conf.local <<EOF
boot_multicons="YES"
boot_serial="YES"
console="${console}"
EOF
    nasdb ${mnt} "update system_advanced set adv_serialconsole = 1"
}

mount_disk()
{
	local _mnt

	if [ $# -ne 1 ]; then
		return 1
	fi

	_mnt="$1"
	mkdir -p "${_mnt}"
	mount -t zfs -o noatime ${BOOT_POOL}/ROOT/${BENAME} ${_mnt}
	mkdir -p ${_mnt}/data
	return 0
}

clear_pool_label()
{
    local _part=$1

    zpool labelclear -f /dev/${_part} 2>/dev/null || true
}

create_partitions()
{
    local _disk="$1"
    local _size="$2"

    if [ -n "${_size}" ]; then
	# Round ZFS partition size down to a multiple of 16 MiB (2^24),
	# leaving units in MiB (2^20).
	_size="-s $(( (_size >> 24) << 4 ))m"
    fi
    if gpart create -s GPT ${_disk}; then
	if [ "$BOOTMODE" = "UEFI" ] ; then
	  # EFI Mode
	  sysctl kern.geom.debugflags=16
	  sysctl kern.geom.label.disk_ident.enable=0
	  if gpart add -s 260m -t efi ${_disk}; then
	    clear_pool_label ${_disk}p1
	    if ! newfs_msdos -F 16 /dev/${_disk}p1 ; then
	      return 1
	    fi
	  fi
	else
	  # BIOS Mode
          if ! gpart add -t freebsd-boot -i 1 -s 512k ${_disk}; then
	    return 1
	  fi
	  clear_pool_label ${_disk}p1
	fi

	if is_swap_safe; then
	    gpart add -t freebsd-swap -a 4k -s 16g -i 3 ${_disk}
	    clear_pool_label ${_disk}p3
	fi
	if gpart add -t freebsd-zfs -a 4k -i 2 ${_size} ${_disk}; then
	    clear_pool_label ${_disk}p2
	    return 0
	fi
    fi
    return 1
}

get_minimum_size()
{
    local _min=0
    local _disk
    local _size

    for _disk
    do
	_size=""
	if create_partitions ${_disk} 1>&2; then
	    _size=$(diskinfo ${_disk}p2 | cut -f 3)
	    gmirror destroy -f swap || true
	    gpart destroy -F ${_disk} 1>&2
	fi
	if [ -z "${_size}" ]; then
	    echo "Could not do anything with ${_disk}, skipping" 1>&2
	    continue
	fi
	if [ ${_min} -eq 0 -o ${_size} -lt ${_min} ]; then
	    _min=${_size}
	fi
    done

    echo ${_min}
}

# Minimum required space for an installation.
# Docs state 8 GiB is the bare minimum, but we specify 8 GB here for wiggle room.
# That should leave enough slop for alignment, boot partition, etc.
: ${MIN_ZFS_PARTITION_SIZE:=$((8 * GB))}; readonly MIN_ZFS_PARTITION_SIZE

partition_disks()
{
    local _disks _disksparts
    local _mirror
    local _minsize
    local _size

    _disks=$*

    check_is_swap_safe ${_disks}

    gmirror destroy -f swap || true

    # Erase both typical metadata area.
    for _disk in ${_disks}; do
	gpart destroy -F ${_disk} >/dev/null 2>&1 || true
	dd if=/dev/zero of=/dev/${_disk} bs=1m count=2 >/dev/null
	_size=$(diskinfo ${_disk} | cut -f 3)
	dd if=/dev/zero of=/dev/${_disk} bs=1m oseek=$((_size / MiB - 2)) >/dev/null || true
    done

    _minsize=$(get_minimum_size ${_disks})

    if [ ${_minsize} -lt ${MIN_ZFS_PARTITION_SIZE} ]; then
	echo "Disk is too small to install ${AVATAR_PROJECT}" 1>&2
	return 1
    fi

    _disksparts=$(for _disk in ${_disks}; do
	create_partitions ${_disk} ${_minsize} >&2
	if [ "$BOOTMODE" != "UEFI" ] ; then
	    # Make the disk active
	    gpart set -a active ${_disk} >&2
	fi
	echo ${_disk}p2
    done)

    if [ $# -gt 1 ]; then
	_mirror="mirror"
    else
	_mirror=""
    fi
    # Regardless of upgrade/fresh installation, if we are creating a new pool, it's going to be named after value of NEW_BOOT_POOL
    BOOT_POOL=${NEW_BOOT_POOL}
    zpool create -f -o cachefile=/tmp/zpool.cache -O mountpoint=none -O atime=off -O canmount=off ${BOOT_POOL} ${_mirror} ${_disksparts}
    zfs set compression=on ${BOOT_POOL}
    zfs create -o canmount=off ${BOOT_POOL}/ROOT
    zfs create -o mountpoint=legacy ${BOOT_POOL}/ROOT/${BENAME}

    return 0
}

get_disk_pool_guid()
{
    local disk=$1
    local part="/dev/${disk}p2"

    zdb -l ${part} | awk '/pool_guid:/ { print $2; exit }'
}

# Preserve a copy of an existing FreeNAS install, assumed to be
# mounted at /tmp/data_old.
preserve_data()
{
    local i

    cp -pR /tmp/data_old/data/. /tmp/data_preserved

    # Don't want to keep the old pkgdb around, since we're
    # nuking the filesystem
    rm -rf /tmp/data_preserved/pkgdb

    if [ -d /tmp/data_old/root/.ssh ]; then
	cp -pR /tmp/data_old/root/.ssh /tmp/
    fi

    if [ -d /tmp/data_old/usr/local/fusionio ]; then
	cp -pR /tmp/data_old/usr/local/fusionio /tmp/
    fi

    if [ -d /tmp/data_old/boot/modules ]; then
	mkdir -p /tmp/modules
	for i in `ls /tmp/data_old/boot/modules`
	do
	    cp -p /tmp/data_old/boot/modules/$i /tmp/modules/
	done
    fi

    if [ -f /tmp/data_old/conf/base/etc/hostid ]; then
	cp -p /tmp/data_old/conf/base/etc/hostid /tmp/
    fi

    if [ -f /tmp/data_old/boot.config ]; then
	cp /tmp/data_old/boot.config /tmp/
    fi

    if [ -f /tmp/data_old/boot/loader.conf.local ]; then
	cp /tmp/data_old/boot/loader.conf.local /tmp/
    fi

    return 0
}

disk_is_freenas()
{
    local disk="$1"
    local part="/dev/${disk}p2"
    local pool_guid=""
    local boot_env=""

    # Old style upgrades are no longer supported.
    if [ -c /dev/${disk}s4 ]; then
	return 1
    fi

    # Make sure this is a FreeNAS boot pool.
    local disk_data=$(zdb -l ${part})
    echo ${disk_data} | grep -qF "name: '${BOOT_POOL}'"
    if [ $? -eq 1 ]; then
        echo ${disk_data} | grep -qF "name: 'freenas-boot'" || return 1
        BOOT_POOL="freenas-boot"
    fi

    # Import the pool by GUID in case there are multiple ${BOOT_POOL} pools.
    pool_guid=$(get_disk_pool_guid ${disk})
    zpool import -N -f ${pool_guid} || return 1

    # We could give the user a list of the boot environments to choose from,
    # but for now we just use the active boot environment for the pool.
    boot_env=$(zpool get -Ho value bootfs ${BOOT_POOL})
    if [ -z "${boot_env}" ]; then
	zpool export ${BOOT_POOL} || true
	return 1
    fi

    mkdir -p /tmp/data_old
    mount -t zfs "${boot_env}" /tmp/data_old
    if [ $? != 0 ]; then
	zpool export ${BOOT_POOL} || true
	return 1
    fi

    # If the active dataset doesn't have a database file,
    # then it's not FN as far as we're concerned (the upgrade code
    # will go badly).
    # We also check for the Corral database directory.
    if [ ! -f /tmp/data_old/data/freenas-v1.db -o \
	   -d /tmp/data_old/data/freenas.db ]; then
	umount /tmp/data_old || true
	zpool export ${BOOT_POOL} || true
	return 1
    fi

    # Try to preserve some miscellaneous files and directories if they exist.
    preserve_data

    umount /tmp/data_old || return 1
    zpool export ${BOOT_POOL} || return 1
    return 0
}

prompt_password()
{
    local values value password="" password1 password2 _counter _tmpfile="/tmp/pwd.$$"

    cat << __EOF__ > /tmp/dialogconf
bindkey formfield TAB FORM_NEXT
bindkey formfield DOWN FORM_NEXT
bindkey formfield UP FORM_PREV
bindkey formbox DOWN FORM_NEXT
bindkey formbox TAB FORM_NEXT
bindkey formbox UP FORM_PREV
__EOF__

    export DIALOGRC="/tmp/dialogconf"

    while true; do
	dialog --insecure \
	    --output-fd 3 \
	    --visit-items \
	    --passwordform "Enter your root password; cancel for no root password" \
	    10 50 0 \
	    "Password:" 1 1 "" 0 20 25 50 \
	    "Confirm Password:" 2 1 "" 2 20 25 50 \
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
    unset DIALOGRC

    echo -n "${password}" 1>&2
}

create_be()
{
    local mountpoint=$1
    local disk=$2 # More disks may be passed, but we only need one.
    local pool_guid=""

    echo "Creating new Boot-Environment"

    # When upgrading, we will simply create a new BE dataset and install
    # fresh into that, so old datasets are not lost.  The pool is imported
    # by GUID for safety in case multiple ${BOOT_POOL} pools are present.
    pool_guid=$(get_disk_pool_guid ${disk})
    zpool import -N -f ${pool_guid} || return 1

    # Create the new BE
    zfs create -o mountpoint=legacy ${BOOT_POOL}/ROOT/${BENAME} || return 1
    zfs set beadm:keep=True ${BOOT_POOL}/ROOT/${BENAME} || return 1

    # Mount the new BE datasets
    mkdir -p ${mountpoint}
    mount -t zfs ${BOOT_POOL}/ROOT/${BENAME} ${mountpoint} || return 1
    mkdir -p ${mountpoint}/data

    return 0
}

cleanup()
{
    zpool export -f ${BOOT_POOL}
    zpool export -f ${NEW_BOOT_POOL}
}

abort()
{
    set +e +x
    trap - EXIT
    exit 1
}

fail()
{
    local _action=${1}
    shift
    local _disks=${@}

    set +x
    read -p "The ${AVATAR_PROJECT} ${_action} on ${_disks} has failed. Press enter to continue..." junk
    abort
}

doing_upgrade()
{
    test -d /tmp/data_preserved
}

menu_install()
{
    local _action
    local _disklist
    local _tmpfile
    local _answer
    local _items
    local _disk
    local _disks=""
    local _realdisks=""
    local _config_file
    local _desc
    local _list
    local _msg
    local _do_upgrade=""
    local _menuheight
    local _msg
    local _dlv
    local _password
    local whendone=""

    local CD_UPGRADE_SENTINEL NEED_UPDATE_SENTINEL FIRST_INSTALL_SENTINEL
    readonly CD_UPGRADE_SENTINEL="/data/cd-upgrade"
    readonly NEED_UPDATE_SENTINEL="/data/need-update"
    # create a sentinel file for post-fresh-install boots
    readonly FIRST_INSTALL_SENTINEL="/data/first-boot"

    _tmpfile="/tmp/answer"
    TMPFILE=$_tmpfile
    REALDISKS="/tmp/realdisks"

    while getopts "U:P:X:" opt; do
	case "${opt}" in
	    U)	if ${OPTARG}; then _do_upgrade=1 ; else _do_upgrade=0; fi
		;;
	    P)	_password="${OPTARG}"
		;;
	    X)	case "${OPTARG}" in
		    reboot)	whendone=reboot ;;
		    "wait")	whendone=wait ;;
		    halt)	whendone=halt ;;
		    *)		whendone="" ;;
		esac
		;;
	    *)	echo "Unknown option ${opt}" 1>&2
		;;
	esac
    done
    shift $((OPTIND-1))

    if [ $# -gt 0 ]
    then
	_disks="$@"
	INTERACTIVE=false
    else
	INTERACTIVE=true
    fi

    # Make sure we are working from a clean slate.
    cleanup >/dev/null 2>&1

    if ${INTERACTIVE}; then
	pre_install_check || return 0
    fi

    if ${INTERACTIVE}; then
        get_physical_disks_list
        _disklist="${VAL}"

        _list=""
        _items=0
        for _disk in ${_disklist}; do
            _desc=$(get_media_description "${_disk}" | sed "s/'/'\\\''/g")
            _list="${_list} ${_disk} '${_desc}' off"
            _items=$((${_items} + 1))
        done
	    
        _tmpfile="/tmp/answer"
        if [ ${_items} -ge 10 ]; then
            _items=10
            _menuheight=20
        else
            _menuheight=9
            _menuheight=$((${_menuheight} + ${_items}))
        fi
        if [ "${_items}" -eq 0 ]; then
            # Inform the user
            eval "dialog --title 'Choose destination media' --msgbox 'No drives available' 5 60" 2>${_tmpfile}
            abort
        fi

        eval "dialog --title 'Choose destination media' \
            --checklist 'Select one or more drives where $AVATAR_PROJECT should be installed (use arrow keys to navigate to the drive(s) for installation; select a drive with the spacebar).' \
            ${_menuheight} 60 ${_items} ${_list}" 2>${_tmpfile}
        [ $? -eq 0 ] || abort
    fi

    if [ -f "${_tmpfile}" ]; then
	_disks=$(eval "echo `cat "${_tmpfile}"`")
	rm -f "${_tmpfile}"
    fi

    if [ -z "${_disks}" ]; then
	${INTERACTIVE} && dialog --msgbox "You need to select at least one disk!" 6 74
	abort
    fi

    if disk_is_mounted ${_disks} ; then
        ${INTERACTIVE} && dialog --msgbox "The destination drive is already in use!" 6 74
        abort
    fi

    _action="installation"
    _upgrade_type="format"
    # This needs to be re-done.
    # If we're not interactive, then we have
    # to assume _disks is correct.
    # If we do have more than one disk given,
    # we should also do something if they're all
    # freenas disks.  But how do we figure out which
    # one to use?  The current code in disk_is_freenas
    # is very, very heavy -- it actually backs up the
    # data from a freenas installation.  It also does
    # a zpool import.
    for _disk in ${_disks}; do
	if disk_is_freenas ${_disk} ; then
	    if ${INTERACTIVE}; then
		if ask_upgrade ${_disk} ; then
		    _do_upgrade=1
		    _action="upgrade"
		fi
	    else
		if [ "${_do_upgrade}" != "0" ]; then
		    _do_upgrade=1
		    _action="upgrade"
		fi
	    fi
	    # Ask if we want to do a format or inplace upgrade
	    if ${INTERACTIVE}; then
		if ask_upgrade_inplace ; then
		    _upgrade_type="inplace"
		fi
	    fi
	    break
	fi
    done
    # If we haven't set _do_upgrade by now, we're not
    # doing an upgrade.
    if [ -z "${_do_upgrade}" ]; then
	_do_upgrade=0
    fi

    _realdisks=$_disks

    ${INTERACTIVE} && new_install_verify "$_action" "$_upgrade_type" ${_realdisks}
    _config_file="/tmp/pc-sysinstall.cfg"

    if ${INTERACTIVE} && [ "${_do_upgrade}" -eq 0 ]; then
	prompt_password 2> /tmp/password
	if [ $? -eq 0 ]; then
	    _password="$(cat /tmp/password 2> /dev/null)"
	fi
    fi

    if [ ${_do_upgrade} -eq 0 ]; then
	# With the new partitioning, disk_is_freenas may
	# copy /data.  So if we don't need it, remove it,
	# or else it'll do an update anyway.  Oops.
	rm -rf /tmp/data_preserved
    fi

    # Start critical section.
    trap "fail ${_action} ${_realdisks}" EXIT
    set -e

    if [ "${_upgrade_type}" = "inplace" ]
    then
        /etc/rc.d/dmesg start
    else
	# Destroy existing partition table, if there is any but tolerate
	# failure.
	for _disk in ${_realdisks}; do
	    gpart destroy -F ${_disk} || true
	done
    fi

    # Run pc-sysinstall against the config generated

    # Hack #1
    export ROOTIMAGE=1
    # Hack #2
    ls $(get_product_path) > /dev/null

    if [ "${_upgrade_type}" = "inplace" ]
    then
      # Set the boot-environment name
      BENAME="default-`date +%Y%m%d-%H%M%S`"
      export BENAME

      # When doing in-place upgrades, we can keep the old zpool
      # and instead do a new BE creation.
      create_be /tmp/data ${_realdisks}
    else
      # Set the boot-environment name
      BENAME="default"
      export BENAME

      if echo ${_disks} | grep -q "raid/"; then
	graid delete ${_disks}
      fi

      if [ -n "$(kenv grub.platform 2>/dev/null)" ] ; then
        if [ "$(kenv grub.platform)" = "efi" ] ; then
          BOOTMODE="UEFI"
        else
          BOOTMODE="BIOS"
	fi
      else
        BOOTMODE=$(sysctl -n machdep.bootmethod)
      fi
      if ${INTERACTIVE}; then
        # Prompt for UEFI or BIOS mode
        if ask_boot_method
        then
          BOOTMODE="UEFI"
	else
	  BOOTMODE="BIOS"
        fi
      fi
      export BOOTMODE

      # We repartition on fresh install or on upgrade when requested.
      # This destroys all of the pool data and ensures a clean filesystem.
      partition_disks ${_realdisks}
      mount_disk /tmp/data
    fi

    if doing_upgrade; then
	cp -pR /tmp/data_preserved/. /tmp/data/data
	# We still need the newer version we are upgrading to's
	# factory-v1.db, else issuing a factory-restore on the
	# newly upgraded system completely borks the system.
	cp /data/factory-v1.db /tmp/data/data/
	chown www:www /tmp/data/data/factory-v1.db
    else
	cp -R /data/* /tmp/data/data
	chown -R www:www /tmp/data/data
    fi

    local OS=TrueNAS

    # Tell it to look in /.mount for the packages.
    /usr/local/bin/freenas-install -P /.mount/${OS}/Packages -M /.mount/${OS}-MANIFEST /tmp/data

    rm -f /tmp/data/conf/default/etc/fstab /tmp/data/conf/base/etc/fstab
    ln /tmp/data/etc/fstab /tmp/data/conf/base/etc/fstab || echo "Cannot link fstab"
    if doing_upgrade; then
	if [ -f /tmp/hostid ]; then
            cp -p /tmp/hostid /tmp/data/conf/base/etc
	fi
	if [ -d /tmp/.ssh ]; then
            cp -pR /tmp/.ssh /tmp/data/root/
	fi

	# TODO: this needs to be revisited.
	if [ -d /tmp/modules ]; then
            for i in `ls /tmp/modules`
            do
		# If it already exists, simply don't copy it.
		cp -np /tmp/modules/$i /tmp/data/boot/modules || true
            done
	fi
	if [ -d /tmp/fusionio ]; then
            cp -pR /tmp/fusionio /tmp/data/usr/local/
	fi
	if [ -f /tmp/boot.config ]; then
	    cp /tmp/boot.config /tmp/data/
	fi
	if [ -f /tmp/loader.conf.local ]; then
	    cp /tmp/loader.conf.local /tmp/data/boot/
	    # TODO: #7042 - Don't use debug kernel
	    sed -i '' -e 's,^module_path=.*,module_path="/boot/kernel;/boot/modules;/usr/local/modules",g' \
		-e '/^kernel=.*/d' /tmp/data/boot/loader.conf /tmp/data/boot/loader.conf.local
	fi
    fi

    # To support Xen, we need to disable HPET.
    if [ "$(/tmp/data/usr/local/sbin/dmidecode -s system-product-name)" = "HVM domU" ]; then
	if ! grep -q 'hint.hpet.0.clock' /tmp/data/boot/loader.conf.local 2>/dev/null ; then
	    echo 'hint.hpet.0.clock="0"' >> /tmp/data/boot/loader.conf.local
	fi
    fi

    # beadm will need a devfs
    mount -t devfs devfs /tmp/data/dev
    # Create a temporary /var
    mount -t tmpfs tmpfs /tmp/data/var
    chroot /tmp/data /usr/sbin/mtree -deUf /etc/mtree/BSD.var.dist -p /var
    # We need this hack due to sqlite3 called from rc.conf.local.
    chroot /tmp/data /sbin/ldconfig /usr/local/lib
    chroot /tmp/data /etc/rc.d/ldconfig forcestart
    # Save current serial console settings into database.
    save_serial_settings /tmp/data
    # Set default boot filesystem
    zpool set bootfs=${BOOT_POOL}/ROOT/${BENAME} ${BOOT_POOL}
    install_loader /tmp/data ${_realdisks}

    if doing_upgrade; then
	# Instead of sentinel files, let's just migrate!
	# Unfortunately, this doesn't seem to work well.
	# This should be investigated.
#	chroot /tmp/data /bin/sh -c "/usr/bin/yes | \
#		/usr/local/bin/python
#		      /usr/local/www/freenasUI/manage.py migrate --all --merge"
	# Create upgrade sentinel files
	: > /tmp/data/${CD_UPGRADE_SENTINEL}
	: > /tmp/data/${NEED_UPDATE_SENTINEL}
	${INTERACTIVE} && dialog --msgbox "The installer has preserved your database file.
$AVATAR_PROJECT will migrate this file, if necessary, to the current format." 6 74
    else
	if [ -n "${_password}" ]; then
		# Set the root password
		chroot /tmp/data /etc/netcli reset_root_pw "${_password}"
	fi
    fi
    : > /tmp/data/${FIRST_INSTALL_SENTINEL}

    # Finally, before we unmount, start a scrub.
    # zpool scrub ${BOOT_POOL} || true

    umount /tmp/data/dev
    umount /tmp/data/var
    umount /tmp/data/

    # End critical section.
    set +e

    trap - EXIT

    _msg="The $AVATAR_PROJECT $_action on ${_realdisks} succeeded!\n"
    _dlv=`/sbin/sysctl -n vfs.nfs.diskless_valid 2> /dev/null`
    if [ ${_dlv:=0} -ne 0 ]; then
        _msg="${_msg}Please reboot, and change BIOS boot order to *not* boot over network."
    else
        _msg="${_msg}Please reboot, then remove the installation media."
    fi
    if ${INTERACTIVE}; then
	dialog --msgbox "$_msg" 6 74
    elif [ -n "${whendone}" ]; then
	case "${whendone}" in
	    halt)	halt -p ;;
	    "wait")	dialog --msgbox "$_msg" 6 74 ;;
	esac
	return 0
    fi

    return 0
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

    if [ $# -gt 0 ]; then
	# $1 will have the device name
	menu_install "$@"
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
        _number=`cat "${_tmpfile}"`
        case "${_number}" in
            1) menu_install ;;
            2) menu_shell ;;
            3) menu_reboot ;;
            4) menu_shutdown ;;
            5) menu_test ;;
        esac
        # Unset cached setting
        unset SWAP_IS_SAFE
    done
}

# Parse a config file.
# We don't do much in the way of error checking.
# Format is very simple:
# <opt>=<value>
# <value> may be a list (e.g., disk devices)
# The output is suitable to be used as the arguments
# to main(), which will directl ycall menu_install().

yesno()
{
    # Output "true" or "false" depending on the argument
    if [ $# -ne 1 ]; then
	echo "false"
	return 0
    fi
    case "$1" in
	[yY][eE][sS] | [tT][rR][uU][eE])	echo true ;;
	*)	echo false;;
    esac
    return 0
}

getsize()
{
    # Given a size specifier, convert it to bytes.
    # No suffix, or a suffix of "[bBcC]", means bytes;
    # [kK] is 1024, etc.
    if [ $# -ne 1 ]; then
	echo 0
	return 0
    fi
    case "$1" in
	*[bB][cC])	expr "$1" : "^\([0-9]*\)[bB][cC]" || echo 0;;
	*[kK])	expr $(expr "$1" : "^\([0-9]*\)[kK]") \* 1024 || echo 0;;
	*[mM])	expr $(expr "$1" : "^\([0-9]*\)[gG]") \* 1024 \* 1024 || echo 0;;
	*[gG])	expr $(expr "$1" : "^\([0-9]*\)[gG]") \* 1024 \* 1024 \* 1024 || echo 0;;
	*[tT])	expr $(expr "$1" : "^\([0-9]*\)[tT]") \* 1024 \* 1024 \* 1024 \* 1024 || echo 0;;
	*) expr "$1" : "^\([0-9]*\)$" || echo 0;;
    esac
    return 0
}

parse_config()
{
    local _conf="/etc/install.conf"
    local _diskList=""
    local _minSize=""
    local _maxSize=""
    local _mirror=false
    local _forceMirror=false
    local _upgrade=""
    local _output=""
    local _maxDisks=""
    local _cmd
    local _args
    local _boot
    local _disk
    local _diskSize
    local _diskCount=0
    local password=""
    local whenDone=""

    while read line
    do
	if expr "${line}" : "^#" > /dev/null
	then
	    continue
	fi
	if ! expr "${line}" : "^[a-zA-Z]*=" > /dev/null
	then
	    continue
	fi
	_cmd=$(expr "${line}" : "^\([^=]*\)=.*")
	_args=$(expr "${line}" : "^[^=]*=\(.*\)$")
	case "${_cmd}" in
	    password)	password="${_args}" ;;
	    whenDone)	case "${_args}" in
			    reboot | wait | halt)	whenDone=${_args} ;;
			    *)	whenDone="" ;;
			esac
			;;
	    minDiskSize)	_minSize=$(getsize "${_args}") ;;
	    maxDiskSize)	_maxSize=$(getsize "${_args}") ;;
	    diskCount)		_maxDisks=${_args} ;;
	    upgrade)	_upgrade=$(yesno "${_args}") ;;
	    disk|disks)	_diskList="${_args}" ;;
	    mirror)	case "${_args}" in
			    [fF][oO][rR][cC][eE])	_mirror=true ; _forceMirror=true ;;
			    *)	_mirror=$(yesno "${_args}") ;;
			esac
			;;
	esac
    done < ${_conf}
    # Okay, done reading the config file
    # Now to go through and handle the settings.
    # Order is important here.
    # But the first thing we want to do is determine our
    # boot disk, so we can exclude it later.
    # For the install, the mount situation is complex,
    # but we want to look for a label of "INSTALL" and find
    # out the device for that.
    _boot=$(glabel status | awk '/INSTALL/ { print $3 }')
    if [ -n "${_upgrade}" ]; then
	# Option to do an upgrade
	_output="-U ${_upgrade}"
    fi
    if [ -n "${password}" ]; then
	# Set the root password
	_output="${_output} -P \"${password}\""
    fi
    if [ -n "${whenDone}" ]; then
	# What to do when finished installing
	_output="${_output} -X ${whenDone}"
    fi
    if [ -z "${_diskList}" ]; then
	# No disks specified in the config file
	# So just get the list from the kernel.
	# We'll be filtering it below
	_diskList=$(sysctl -n kern.disks)
    fi
    for _disk in ${_diskList}
    do
	if [ "${_disk}" = "${_boot}" ]; then
	    continue
	fi
	_diskSize=$(diskinfo ${_disk} | cut -f 3)
	if [ -n "${_minSize}" ] && [ "${_diskSize}" -lt "${_minSize}" ]; then
	    continue
	fi
	if [ -n "${_maxSize}" ] && [ "${_diskSize}" -gt "${_maxSize}" ]; then
	    continue
	fi
	_output="${_output} ${_disk}"
	_diskCount=$(expr ${_diskCount} + 1)
	if ! ${_mirror}; then
	    break
	fi
	if [ -n "${_maxDisks}" ] && [ "${_diskCount}" -eq "${_maxDisks}" ]; then
	    break;
	fi
    done
    # Now we should have some disks.
    if [ ${_diskCount} -eq 0 ]; then
	echo "No disks available that match the criteria" 1>&2
	return 1
    fi
    if ${_forceMirror} && [ ${_diskCount} -eq 1 ]; then
	echo "Only one disk found, but mirror required for install" 1>&2
	return 1
    fi
    echo ${_output}
    return 0
}

if [ -f /etc/install.conf ]; then
    CONFIG_OUTPUT=$(parse_config)
    if [ $? -ne 0 ]; then
	read -p "Config file parsing failed to find specified media " foo
	echo "Dropping into a shell"
	/bin/sh
	exit 1
    elif [ -n "${CONFIG_OUTPUT}" ]; then
	set -- ${CONFIG_OUTPUT}
	menu_install "$@"
	menu_reboot
    fi
fi

main "$@"
