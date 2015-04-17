#!/bin/sh

# vim: noexpandtab ts=8 sw=4 softtabstop=4

# Setup a semi-sane environment
PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin:/rescue
export PATH
HOME=/root
export HOME
TERM=${TERM:-cons25}
export TERM
GRUB_TERMINAL_OUTPUT="console serial"
export GRUB_TERMINAL_OUTPUT

. /etc/avatar.conf

is_truenas()
{

    test "$AVATAR_PROJECT" = "TrueNAS"
    return $?
}

do_sata_dom()
{

    if ! is_truenas ; then
	return 1
    fi
    install_sata_dom_prompt
    return $?
}

get_product_path()
{
    echo /cdrom /.mount
}

get_image_name()
{
    find $(get_product_path) -name "$AVATAR_PROJECT-$AVATAR_ARCH.img.xz" -type f
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

build_config_old()
{
    # build_config ${_disk} ${_image} ${_config_file}

    local _disk=$1
    local _image=$2
    local _config_file=$3

    cat << EOF > "${_config_file}"
# Added to stop pc-sysinstall from complaining
installMode=fresh
installInteractive=no
installType=FreeBSD
installMedium=dvd
packageType=tar

disk0=${_disk}
partition=image
image=${_image}
bootManager=bsd
commitDiskPart
EOF
}
build_config()
{
    # build_config ${_disk} ${_image} ${_config_file}

    local _disk=$1
    local _image=$2
    local _config_file=$3

    cat << EOF > "${_config_file}"
# Added to stop pc-sysinstall from complaining
installMode=fresh
installInteractive=no
installType=FreeBSD
installMedium=dvd
packageType=tar

disk0=${_disk}
partscheme=GPT
partition=all
bootManager=bsd
commitDiskPart
EOF
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
    VAL=`sysctl -n kern.disks`

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
    VAL=""
    if [ -n "${_media}" ]; then
        _description=`pc-sysinstall disk-list -c |grep "^${_media}:"\
            | awk -F':' '{print $2}'|sed -E 's|.*<(.*)>.*$|\1|'`
	# if pc-sysinstall doesn't know anything about the device
	# (raid drives) then fill in for it.
	if [ -z "$_description" ] ; then
		_description="Unknown Device"
	fi
        _cap=`diskinfo ${_media} | awk '{
            capacity = $3;
            if (capacity >= 1099511627776) {
                printf("%.1f TiB", capacity / 1099511627776.0);
            } else if (capacity >= 1073741824) {
                printf("%.1f GiB", capacity / 1073741824.0);
            } else if (capacity >= 1048576) {
                printf("%.1f MiB", capacity / 1048576.0);
            } else {
                printf("%d Bytes", capacity);
        }}'`
        VAL="${_description} -- ${_cap}"
    fi
    export VAL
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

    local _disks="$*"
    local _tmpfile="/tmp/msg"
    cat << EOD > "${_tmpfile}"
WARNING:
- This will erase ALL partitions and data on ${_disks}.
- You can't use ${_disks} for sharing data.

NOTE:
- Installing on flash media is preferred to installing on a
  hard drive.

Proceed with the ${_type}?
EOD
    _msg=`cat "${_tmpfile}"`
    rm -f "${_tmpfile}"
    dialog --clear --title "$AVATAR_PROJECT ${_type}" --yesno "${_msg}" 13 74
    [ $? -eq 0 ] || exit 1
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

install_grub() {
	local _disk _disks
	local _mnt

	_mnt="$1"
	shift

	_disks="$*"

	# Install grub
	chroot ${_mnt} /sbin/zpool set cachefile=/boot/zfs/rpool.cache freenas-boot
	chroot ${_mnt} /etc/rc.d/ldconfig start
	/usr/bin/sed -i.bak -e 's,^ROOTFS=.*$,ROOTFS=freenas-boot/ROOT/default,g' ${_mnt}/usr/local/sbin/beadm ${_mnt}/usr/local/etc/grub.d/10_ktrueos
	# Having 10_ktruos.bak in place causes grub-mkconfig to
	# create two boot menu items.  So let's move it out of place
	mkdir -p /tmp/bakup
	mv ${_mnt}/usr/local/etc/grub.d/10_ktrueos.bak /tmp/bakup
	for _disk in ${_disks}; do
	    chroot ${_mnt} /usr/local/sbin/grub-install --modules='zfs part_gpt' /dev/${_disk}
	done
	chroot ${_mnt} /usr/local/sbin/beadm activate default
	chroot ${_mnt} /usr/local/sbin/grub-mkconfig -o /boot/grub/grub.cfg > /dev/null 2>&1
	# And now move the backup files back in place
	mv ${_mnt}/usr/local/sbin/beadm.bak ${_mnt}/usr/local/sbin/beadm
	mv /tmp/bakup/10_ktrueos.bak ${_mnt}/usr/local/etc/grub.d/10_ktrueos
	return 0
}

mount_disk() {
	local _mnt

	if [ $# -ne 1 ]; then
		return 1
	fi

	_mnt="$1"
	mkdir -p "${_mnt}"
	mount -t zfs -o noatime freenas-boot/ROOT/default ${_mnt}
	mkdir -p ${_mnt}/boot/grub
	mount -t zfs -o noatime freenas-boot/grub ${_mnt}/boot/grub
	mkdir -p ${_mnt}/data
	return 0
}
	
partition_disk() {
	local _disks _disksparts
	local _mirror

	_disks=$*

	_disksparts=$(for _disk in ${_disks}; do
	    gpart destroy -F ${_disk} > /dev/null 2>&1 || true
	    zpool labelclear -f ${_disk} > /dev/null 2>&1 || true
	    # Get rid of any MBR.  Shouldn't be necessary,
	    # but caching seems to have caused problems.
	    dd if=/dev/zero of=/dev/${_disk} bs=1m count=1 >&2

	    # Now create a GPT partition.
	    gpart create -s gpt ${_disk} >&2
	    # For grub
	    gpart add -t bios-boot -i 1 -s 512k ${_disk} >&2

	    # If we're truenas, add swap
	    if is_truenas; then
	        # Is this correct?
	        gpart add -t freebsd-swap -i 3 -s 16g ${_disk} >&2
	    fi
	    # The rest of the disk
	    gpart add -t freebsd-zfs -i 2 -a 4k ${_disk} >&2

	    # And make it active
	    gpart set -a active ${_disk} >&2

	    echo ${_disk}p2
	done)

	if [ $# -gt 1 ]; then
	    _mirror="mirror"
	else
	    _mirror=""
	fi
	zpool create -f -o cachefile=/tmp/zpool.cache -o version=28 -O mountpoint=none -O atime=off -O canmount=off freenas-boot ${_mirror} ${_disksparts}
	zpool set feature@lz4_compress=enabled freenas-boot
	zfs set compress=lz4 freenas-boot
	zfs create -o canmount=off freenas-boot/ROOT
	zfs create -o mountpoint=legacy freenas-boot/ROOT/default
	zfs create -o mountpoint=legacy freenas-boot/grub

	return 0
}

make_swap()
{
    local _swapparts

    _swapparts=$(for _disk in $*; do echo ${_disk}p3; done)
    gmirror label -b prefer swap ${_swapparts}
    echo "/dev/mirror/swap.eli		none			swap		sw		0	0" > /tmp/data/data/fstab.swap
}

disk_is_freenas()
{
    local _disk="$1"
    local _rv=1
    local upgrade_style=""
    local os_part=""
    local data_part=""

    # We have two kinds of potential upgrades here.
    # The old kind, with 4 slices, and the new kind,
    # with two partitions.

    mkdir -p /tmp/data_old
    if [ -c /dev/${_disk}s4 ]; then
	os_part=/dev/${_disk}s1a
	data_part=/dev/${_disk}s4
	upgrade_style="old"
    elif [ -c /dev/${_disk}p2 ]; then
	os_part=/dev/${_disk}p2
	upgrade_style="new"
    else
	return 1
    fi

    if [ "${upgrade_style}" = "new" ]; then
	# This code is very clumsy.  There
	# should be a way to structure it such that
	# all of the cleanup happens as we want it to.
	if zdb -l ${os_part} | grep "name: 'freenas-boot'" > /dev/null ; then
	    :
	else
	    return 1
	fi
	zpool import -N -f freenas-boot || return 1
	# Now we want to figure out which dataset to use.
	# We'll mount freenas-boot/grub, and then look for "default=" in
	# grub.cfg
	# Of course, if grub.cfg doesn't exist, this isn't a freenas pool, just
	# a pool masquerading as us.
	if ! mount -t zfs freenas-boot/grub /tmp/data_old; then
	    zpool export freenas-boot
	    return 1
	fi
	if [ ! -f /tmp/data_old/grub.cfg ]; then
	    umount /tmp/data_old
	    rmdir /tmp/data_old
	    zpool export freenas-boot
	    return 1
	fi
	# There should always be a "set default=" line in a grub.cfg
	# that we created.
	if grep -q '^set default=' /tmp/data_old/grub.cfg ; then
	    DF=$(grep '^set default=' /tmp/data_old/grub.cfg | tail -1 | sed 's/^set default="\(.*\)"$/\1/')
	    case "${DF}" in
		0)	# No default, use "default"
		    DS=default ;;
                *${AVATAR_PROJECT}*)    # Default dataset
                    DS=$(expr "${DF}" : "${AVATAR_PROJECT} (\(.*\)) .*") ;;
		*) DS="" ;;
	    esac
	    umount /tmp/data_old
	    if [ -n "${DS}" ]; then
		# Okay, mount this pool
		if mount -t zfs freenas-boot/ROOT/"${DS}" /tmp/data_old; then
		    cp -pR /tmp/data_old/data/. /tmp/data_preserved
		    # Don't want to keep the old pkgdb around, since we're
		    # nuking the filesystem
		    rm -rf /tmp/data_preserved/pkgdb
		    if [ -f /tmp/data_old/conf/base/etc/hostid ]; then
			cp -p /tmp/data_old/conf/base/etc/hostid /tmp/
		    fi
		    if [ -d /tmp/data_old/root/.ssh ]; then
			cp -pR /tmp/data_old/root/.ssh /tmp/
		    fi
		    if [ -d /tmp/data_old/boot/modules ]; then
			mkdir -p /tmp/modules
			for i in `ls /tmp/data_old/boot/modules`
			do
			    cp -p /tmp/data_old/boot/modules/$i /tmp/modules/
			done
		    fi
		    if [ -d /tmp/data_old/usr/local/fusionio ]; then
			cp -pR /tmp/data_old/usr/local/fusionio /tmp/
		    fi
		    if [ -f /tmp/data_old/boot.config ]; then
			cp /tmp/data_old/boot.config /tmp/
		    fi
		    if [ -f /tmp/data_old/boot/loader.conf.local ]; then
			cp /tmp/data_old/boot/loader.conf.local /tmp/
		    fi
		    umount /tmp/data_old || return 1
		    zpool export freenas-boot || return 1
		    return 0
		fi
	    fi
	    zpool export freenas-boot || true
	    return 1
	else
	    umount /tmp/data_old || return 1
	    zpool export freenas-boot || true
	    return 1
	fi
    fi

    # This is now legacy code, to support the old
    # partitioning scheme (freenas-9.2 and earlier)
    if ! mount "${data_part}" /tmp/data_old ; then
	return 1
    fi

    ls /tmp/data_old > /tmp/data_old.ls
    if [ -f /tmp/data_old/freenas-v1.db ]; then
        _rv=0
    fi
    # XXX side effect, shouldn't be here!
    cp -pR /tmp/data_old/. /tmp/data_preserved
    umount /tmp/data_old
    if [ $_rv -eq 0 ]; then
	# For GUI upgrades, we only have one OS partition
	# that has conf/base/etc.  For ISO upgrades, we
	# have two, but only one is active.
	slice=$(gpart show ${_disk} | grep -F '[active]' | awk ' { print $3;}')
	if [ -z "${slice}" ]; then
	    # We don't have an active slice, so something is wrong.
	    return 1
	fi
	mount /dev/${_disk}s${slice}a /tmp/data_old
	ls /tmp/data_old > /dev/null
	if [ ! -d /tmp/data_old/conf/base/etc ]
	then
	    # Mount the other partition
	    if [ "${slice}" -eq 1 ]; then
		slice=2
	    else
		slice=1
	    fi
	    umount /tmp/data_old
	    mount /dev/${_disk}s${slice}a /tmp/data_old
	    ls /tmp/data_old > /dev/null
	fi
	if [ -f /tmp/data_old/conf/base/etc/hostid ]; then
	    cp -p /tmp/data_old/conf/base/etc/hostid /tmp/
	fi
        if [ -d /tmp/data_old/root/.ssh ]; then
            cp -pR /tmp/data_old/root/.ssh /tmp/
        fi
        if [ -d /tmp/data_old/boot/modules ]; then
            mkdir -p /tmp/modules
            for i in `ls /tmp/data_old/boot/modules`
            do
                cp -p /tmp/data_old/boot/modules/$i /tmp/modules/
            done
        fi
        if [ -d /tmp/data_old/usr/local/fusionio ]; then
            cp -pR /tmp/data_old/usr/local/fusionio /tmp/
        fi
	if [ -f /tmp/data_old/boot.config ]; then
	    cp /tmp/data_old/boot.config /tmp/
	fi
	if [ -f /tmp/data_old/boot/loader.conf.local ]; then
	    cp /tmp/data_old/boot/loader.conf.local /tmp/
	fi
        umount /tmp/data_old
    fi
    rmdir /tmp/data_old
    return $_rv
}

prompt_password() {

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
    unset DIALOGRC


    echo -n "${password}" 1>&2

}

menu_install()
{
    local _action
    local _disklist
    local _tmpfile
    local _answer
    local _cdlist
    local _items
    local _disk
    local _disks=""
    local _realdisks=""
    local _disk_old
    local _config_file
    local _desc
    local _list
    local _msg
    local _satadom
    local _i
    local _do_upgrade
    local _menuheight
    local _msg
    local _dlv
    local _password
    local os_part
    local data_part
    local upgrade_style

    local readonly CD_UPGRADE_SENTINEL="/data/cd-upgrade"
    local readonly NEED_UPDATE_SENTINEL="/data/need-update"
    # create a sentinel file for post-fresh-install boots
    local readonly FIRST_INSTALL_SENTINEL="/data/first-boot"
    local readonly POOL="freenas-boot"

    _tmpfile="/tmp/answer"
    TMPFILE=$_tmpfile
    REALDISKS="/tmp/realdisks"

    if [ $# -gt 0 ]; then
	_disks="$@"
	INTERACTIVE=false
    else
	INTERACTIVE=true
    fi

    if do_sata_dom
    then
	_satadom="YES"
    else
	_satadom=""
	if ${INTERACTIVE}; then
	    get_physical_disks_list
	    _disklist="${VAL}"

	    _list=""
	    _items=0
	    for _disk in ${_disklist}; do
		get_media_description "${_disk}"
		_desc="${VAL}"
		_list="${_list} ${_disk} '${_desc}' off"
		_items=$((${_items} + 1))
	    done
	    
	    _tmpfile="/tmp/answer"
	    if [ ${_items} -ge 10 ]; then
		_items=10
		_menuheight=20
	    else
		_menuheight=8
		_menuheight=$((${_menuheight} + ${_items}))
	    fi
	    if [ "${_items}" -eq 0 ]; then
		# Inform the user
		eval "dialog --title 'Choose destination media' --msgbox 'No drives available' 5 60" 2>${_tmpfile}
		return 0
	    fi

	    eval "dialog --title 'Choose destination media' \
	      --checklist 'Select one or more drives where $AVATAR_PROJECT should be installed (use arrow keys to navigate to the drive(s) for installation; select a drive with the spacebar).' \
	      ${_menuheight} 60 ${_items} ${_list}" 2>${_tmpfile}
	    [ $? -eq 0 ] || exit 1
	fi
    fi # ! do_sata_dom

    if [ -f "${_tmpfile}" ]; then
	_disks=$(eval "echo `cat "${_tmpfile}"`")
	rm -f "${_tmpfile}"
    fi

    if [ -z "${_disks}" ]; then
	${INTERACTIVE} && dialog --msgbox "You need to select at least one disk!" 6 74
	exit 1
    fi

    if disk_is_mounted ${_disks} ; then
        ${INTERACTIVE} && dialog --msgbox "The destination drive is already in use!" 6 74
        exit 1
    fi

    _do_upgrade=0
    _action="installation"
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
	    # Always doing an upgrade in this case
	    _do_upgrade=1
	    _action="upgrade"
	fi
	if [ -c /dev/${_disk}s4 ]; then
	    upgrade_style="old"
	elif [ -c /dev/${_disk}p2 ]; then
	    upgrade_style="new"
	else
	    echo "Unknown upgrade style" 1>&2
	    exit 1
	fi
	break
    elif [ "${_satadom}" = "YES" -a -c /dev/ufs/TrueNASs4 ]; then
	# Special hack for USB -> DOM upgrades
	_disk_old=`glabel status | grep ' ufs/TrueNASs4 ' | awk '{ print $3 }' | sed -e 's,s4$,,g'`
	if disk_is_freenas ${_disk_old} ; then
	    if ask_upgrade ${_disk_old} ; then
		_do_upgrade=2
		_action="upgrade"
		break
	    fi
	fi
    fi
    done

    if [ "${_satadom}" = "YES" -a -n "$(echo ${_disks}|grep "raid/")" ]; then
	_realdisks=$(cat ${REALDISKS})
    else
	_realdisks=$_disks
    fi


    ${INTERACTIVE} && new_install_verify "$_action" ${_realdisks}
    _config_file="/tmp/pc-sysinstall.cfg"

    if ${INTERACTIVE} && [ "${_do_upgrade}" -eq 0 ]; then
	prompt_password 2> /tmp/password
	if [ $? -eq 0 ]; then
	    _password=$(cat /tmp/password 2> /dev/null)
	fi
    fi

    if [ ${_do_upgrade} -eq 0 ]; then
	# With the new partitioning, disk_is_freenas may
	# copy /data.  So if we don't need it, remove it,
	# or else it'll do an update anyway.  Oops.
	rm -rf /tmp/data_preserved
    fi
    # Start critical section.
    if ${INTERACTIVE}; then
	trap "set +x; read -p \"The $AVATAR_PROJECT $_action on ${_realdisks} has failed. Press any key to continue.. \" junk" EXIT
    else
#	trap "echo \"The ${AVATAR_PROJECT} ${_action} on ${_realdisks} has failed.\" ; sleep 15" EXIT
	trap "set +x; read -p \"The $AVATAR_PROJECT $_action on ${_realdisks} has failed. Press any key to continue.. \" junk" EXIT
    fi
    set -e
#    set -x

    #  _disk, _image, _config_file
    # we can now build a config file for pc-sysinstall
    # build_config  ${_disk} "$(get_image_name)" ${_config_file}

    # For one of the install_worker ISO scripts
    export INSTALL_MEDIA=${_realdisks}
    if [ ${_do_upgrade} -eq 1 ]
    then
        /etc/rc.d/dmesg start
        mkdir -p /tmp/data
	if [ "${upgrade_style}" = "old" ]; then
	    	# For old style, we have two potential
	    	# partitions to look at:  s1a and s2a.
		# 
	    slice=$(gpart show ${_disk} | grep -F '[active]' | awk ' { print $3;}')
	    if [ -z "${slice}" ]; then
		# We don't have an active slice, so something is wrong.
		false
	    fi
	    mount /dev/${_disk}s${slice}a /tmp/data
	    ls /tmp/data > /dev/null
	    if [ ! -d /tmp/data/conf/base/etc ]
	    then
		# Mount the other partition
		if [ "${slice}" -eq 1 ]; then
		    slice=2
		else
		    slice=1
		fi
		umount /tmp/data
		mount /dev/${_disk}s${slice}a /tmp/data
		ls /tmp/data > /dev/null
	    fi
	    # pre-avatar.conf build. Convert it!
	    if [ ! -e /tmp/data/conf/base/etc/avatar.conf ]
	    then
		upgrade_version_to_avatar_conf \
		    /tmp/data/conf/base/etc/version* \
		    /etc/avatar.conf \
		    /tmp/data/conf/base/etc/avatar.conf
	    fi
	elif [ "${upgrade_style}" = "new" ]; then
		zpool import -f -N ${POOL}
		mount -t zfs -o noatime freenas-boot/ROOT/default /tmp/data
	else
		echo "Unknown upgrade style" 1>&2
		false
	fi
	# This needs to be rewritten.
        install_worker.sh -D /tmp/data -m / pre-install
        umount /tmp/data
	if [ "${upgrade_style}" = "new" ]; then
	    zpool export freenas-boot
	fi
        rmdir /tmp/data
    else
        # Run through some sanity checks on new installs ;).. some of the
        # checks won't make sense, but others might (e.g. hardware sanity
        # checks).
        install_worker.sh -D / -m / pre-install

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

    if echo ${_disks} | grep -q "raid/"; then
	graid delete ${_disks}
    fi

    # We repartition even if it's an upgrade.
    # This destroys all of the pool data, and
    # ensures a clean filesystems.
    partition_disk ${_realdisks}
    mount_disk /tmp/data
    
    if [ -d /tmp/data_preserved ]; then
	cp -pR /tmp/data_preserved/. /tmp/data/data
	# we still need the newer version we are upgrading to's
	# factory-v1.db, else issuing a factory-restore on the
	# newly upgraded system completely horks the system
	cp /data/factory-v1.db /tmp/data/data/
	chown www:www /tmp/data/data/factory-v1.db
    else
	cp -R /data/* /tmp/data/data
	chown -R www:www /tmp/data/data
    fi

    local OS=FreeNAS
    if is_truenas; then
        OS=TrueNAS
    fi

    # Tell it to look in /.mount for the packages.
    /usr/local/bin/freenas-install -P /.mount/${OS}/Packages -M /.mount/${OS}-MANIFEST /tmp/data
    
    rm -f /tmp/data/conf/default/etc/fstab /tmp/data/conf/base/etc/fstab
    echo "freenas-boot/grub	/boot/grub	zfs	rw,noatime	1	0" > /tmp/data/etc/fstab
    if is_truenas; then
       make_swap ${_realdisks}
    fi
    ln /tmp/data/etc/fstab /tmp/data/conf/base/etc/fstab || echo "Cannot link fstab"
    if [ "${_do_upgrade}" -ne 0 ]; then
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
		cp -np /tmp/modules/$i /tmp/data/boot/modules
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
    if is_truenas ; then
        install_worker.sh -D /tmp/data -m / install
    fi
    
    # Debugging pause.
    # read foo
    
    # XXX: Fixup
    # tar cf - -C /tmp/data/conf/base etc | tar xf - -C /tmp/data/
    
    # grub and beadm will need a devfs
    mount -t devfs devfs /tmp/data/dev
    # Create a temporary /var
    mount -t tmpfs tmpfs /tmp/data/var
    chroot /tmp/data /usr/sbin/mtree -deUf /etc/mtree/BSD.var.dist -p /var
    # Set default boot filesystem
    zpool set bootfs=freenas-boot/ROOT/default freenas-boot
    install_grub /tmp/data ${_realdisks}
    
#    set +x
    if [ -d /tmp/data_preserved ]; then
	# Instead of sentinel files, let's just migrate!
	# Unfortunately, this doesn't seem to work well.
	# This should be investigated.
#	chroot /tmp/data /bin/sh -c "/usr/bin/yes | \
#		/usr/local/bin/python
#		      /usr/local/www/freenasUI/manage.py migrate --all --merge --delete-ghost-migrations"
	# Create upgrade sentinel files
	: > /tmp/data/${CD_UPGRADE_SENTINEL}
	: > /tmp/data/${NEED_UPDATE_SENTINEL}
	${INTERACTIVE} && dialog --msgbox "The installer has preserved your database file.
#$AVATAR_PROJECT will migrate this file, if necessary, to the current format." 6 74
    elif [ "${_do_upgrade}" -eq 0 ]; then
	if [ -n "${_password}" ]; then
		# Set the root password
		chroot /tmp/data /etc/netcli reset_root_pw ${_password}
	fi
    fi
    : > /tmp/data/${FIRST_INSTALL_SENTINEL}
    # Finally, before we unmount, start a srub.
    # zpool scrub freenas-boot || true

    umount /tmp/data/boot/grub
    umount /tmp/data/dev
    umount /tmp/data/var
    umount /tmp/data/

    # We created a 16m swap partition earlier, for TrueNAS
    # And created /data/fstab.swap as well.
    if is_truenas ; then
#        # Put a swap partition on newly created installation image
#        if [ -e /dev/${_disk}s3 ]; then
#            gpart delete -i 3 ${_disk}
#            gpart add -t freebsd ${_disk}
#            echo "/dev/${_disk}s3.eli		none			swap		sw		0	0" > /tmp/fstab.swap
#        fi
#
#        mkdir -p /tmp/data
#        mount /dev/${_disk}s4 /tmp/data
#        ls /tmp/data > /dev/null
#        mv /tmp/fstab.swap /tmp/data/
#        umount /tmp/data
#        rmdir /tmp/data
    fi

    # End critical section.
    set +e

    trap - EXIT

    _msg="The $AVATAR_PROJECT $_action on ${_realdisks} succeeded!\n"
    _dlv=`/sbin/sysctl -n vfs.nfs.diskless_valid 2> /dev/null`
    if [ ${_dlv:=0} -ne 0 ]; then
        _msg="${_msg}Please reboot, and change BIOS boot order to *not* boot over network."
    else
        _msg="${_msg}Please remove the CDROM and reboot."
    fi
    ${INTERACTIVE} && dialog --msgbox "$_msg" 6 74

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

    if [ $# -eq 1 ]; then
	# $1 will have the device name
	menu_install "$1"
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
    done
}

if is_truenas ; then
    . "$(dirname "$0")/install_sata_dom.sh"
fi

main "$@"
