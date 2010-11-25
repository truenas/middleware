#!/bin/sh

# Setup a semi-sane environment
PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
export PATH
HOME=/root
export HOME
TERM=${TERM:-cons25}
export TERM

get_product_name()
{
    echo "FreeNAS"
}

get_product_arch()
{
    uname -p
}

get_product_path()
{
    echo "/cdrom"
}

get_image_name()
{
    echo "$(get_product_path)/$(get_product_name)-$(get_product_arch)-embedded.xz"
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
partition=image
image=${_image}
bootManager=bsd
commitDiskPart
EOF
}

wait_keypress()
{
    local _tmp
    read -p "Press ENTER to continue." _tmp
}

get_physical_disks_list()
{
    local _disks
    local _list
    local _d

    _list=""
    _disks=`sysctl -n kern.disks`
    for _d in ${_disks}; do
	if echo "${_d}" | grep -vE '^cd' >/dev/null 2>&1; then
	    _list="${_list}${_d} "
	fi
    done

    VAL="${_list}"
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
	_description=`pc-sysinstall disk-list -c |grep "^${_media}"\
	    | awk -F':' '{print $2}'|sed -E 's|.*<(.*)>.*$|\1|'`
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

    _dev="/dev/$1"
    mount -v|grep -E "^${_dev}[sp][0-9]+" >/dev/null 2>&1
    return $?
}


new_install_verify()
{
    local _type="$1" _disk="$2"
    local _tmpfile="/tmp/msg"
    cat << EOD > "${_tmpfile}"
FreeNAS installer for Flash device or HDD.

WARNING: There will be some limitations:
1. This will erase ALL partitions and data on the destination disk
2. You can't use your destination disk for sharing data

Installing on USB key is the preferred way:
It saves you an IDE, SATA or SCSI channel for more hard drives.

Proceed with the ${_type} onto ${_disk}?
EOD
    _msg=`cat "${_tmpfile}"`
    rm -f "${_tmpfile}"
    dialog --title "Start FreeNAS installation" --yesno "${_msg}" 13 74
    if [ "$?" != "0" ]; then
        exit 1
    fi
}

ask_upgrade()
{
    local _disk="$1"
    local _tmpfile="/tmp/msg"
    cat << EOD > "${_tmpfile}"
The FreeNAS installer can preserve your existing parameters, or
it can do a fresh install overwriting the current settings,
configuration, etc.

Would you like to upgrade the installation on ${_disk}?
EOD
    _msg=`cat "${_tmpfile}"`
    rm -f "${_tmpfile}"
    dialog --title "Upgrade this FreeNAS installation" --yesno "${_msg}" 8 74
    return $?
}

disk_is_freenas()
{
    local _disk="$1"
    local _rv=1

    mkdir /tmp/junk
    mount /dev/${_disk}s4 /tmp/junk
    ls /tmp/junk > /tmp/junk.ls
    if [ -f /tmp/junk/freenas-v1.db ]; then
	cp /tmp/junk/freenas-v1.db /tmp/freenas-v1.db
	_rv=0
    fi
    umount /tmp/junk
    if [ $_rv -eq 0 ]; then
	mount /dev/${_disk}s1a /tmp/junk
	cp /tmp/junk/conf/base/etc /tmp/hostis
	umount /tmp/junk
	# ssh keys?
    fi
    rmdir /tmp/junk

    return ${_rv}
}

menu_install()
{
    local _disklist
    local _tmpfile
    local _answer
    local _cdlist
    local _items
    local _disk
    local _config_file
    local _desc
    local _list
    local _msg
    local _i
    local _do_upgrade

    get_physical_disks_list
    _disklist="${VAL}"

    _list=""
    _items=0
    for _disk in ${_disklist}; do
        get_media_description "${_disk}"
        _desc="${VAL}"
        _list="${_list} ${_disk} '${_desc}'"
        _items=$((${_items} + 1))
    done

    _tmpfile="/tmp/answer"
    eval "dialog --title 'Choose destination media' \
          --menu 'Select media where FreeNAS OS should be installed.' \
          15 60 ${_items} ${_list}" 2>${_tmpfile}
    if [ "$?" != "0" ]; then
        exit 1
    fi
    _disk=`cat "${_tmpfile}"`
    rm -f "${_tmpfile}"

    # Debugging seatbelts
    if disk_is_mounted "${_disk}" ; then
        dialog --msgbox "The destination drive is already in use!" 4 74
        exit 1
    fi

    _do_upgrade=0
    if disk_is_freenas ${_disk} ; then
	if ask_upgrade ${_disk} ; then
	    new_install_verify "upgrade" ${_disk}
	    _do_upgrade=1
	else
	    new_install_verify "installation" ${_disk}
	fi
    else
	new_install_verify "installation" ${_disk}
    fi
    _config_file="/tmp/pc-sysinstall.cfg"

    #  _disk, _image, _config_file
    # we can now build a config file for pc-sysinstall
    build_config  ${_disk} "$(get_image_name)" ${_config_file}

    # Run pc-sysinstall against the config generated

    # Hack #1
    export ROOTIMAGE=1
    # Hack #2
    ls /cdrom > /dev/null
    /rescue/pc-sysinstall -c ${_config_file}
    if [ ${_do_upgrade} -eq 1 ]; then
	mkdir /tmp/junk
	mount /dev/${_disk}s4 /tmp/junk
	cp /tmp/freenas-v1.db /tmp/junk
	cp /dev/null /tmp/junk/need-update
	umount /tmp/junk
	mount /dev/${disk}s1a /tmp/junk
	cp /tmp/hostis /tmp/junk/conf/base/etc
	umount /tmp/junk
	# ssh keys
	rmdir /tmp/junk
	dialog --msgbox 'The installer has preserved your database file.  FreeNAS
will migrate this file, if necessary, to the current format.
' 6 74
    fi
    dialog --msgbox 'FreeNAS has been successfully installed on '"${_disk}."'
Please remove the CDROM and reboot this machine.
' 6 74
    return 0
}

menu_shell()
{
    /bin/sh
}

menu_reboot()
{
    echo "Rebooting the system..."
    reboot >/dev/null
}

menu_shutdown()
{
    echo "Halting and powering down..."
    halt -p >/dev/null
}

main()
{
    local _tmpfile="/tmp/answer"
    local _number

    while :; do

	dialog --clear --title "FreeNAS 8.0 Beta Console Setup" --menu "" 12 73 6 \
	    "1" "Install/Upgrade to hard drive/flash device, etc." \
	    "2" "Shell" \
	    "3" "Reboot System" \
	    "4" "Shutdown System" \
	    2> "${_tmpfile}"
	_number=`cat "${_tmpfile}"`
	case "${_number}" in
	    1) menu_install ;;
	    2) menu_shell ;;
	    3) menu_reboot ;;
	    4) menu_shutdown ;;
	esac
    done
}
main
