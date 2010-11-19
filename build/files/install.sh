#!/bin/sh

. /.profile

__FREENAS_DEBUG__=""


get_product_name()
{
	local _product

	_product="FreeNAS"
	VAL="${_product}"

	export VAL
}

get_product_arch()
{
	local _arch=$(uname -p)
	VAL="${_arch}"

	export VAL
}

get_product_path()
{
	local _path

	_path=""
	VAL="${_path}"

	export VAL
}

get_image_name()
{
	local _product
	local _arch
	local _path

	get_product_name
	_product="${VAL}"

	get_product_arch
	_arch="${VAL}"

	get_product_path
	_path="${VAL}"

	VAL="${_path}/${_product}-${_arch}-embedded.xz"
	export VAL
}

build_config()
{
        # build_config ${_disk} ${_image} ${_config_file}

        local _disk=$1
        local _image=$2
        local _config_file=$3
	local _arch=$(uname -p)

        cat << EOF > "${_config_file}"
# Added to stop pc-sysinstall from complaining
installMode=fresh
installInteractive=no
installType=FreeBSD
installMedium=dvd
packageType=tar

disk0=${_disk}
partition=image
image=/cdrom/FreeNAS-${_arch}-embedded.xz
bootManager=bsd
commitDiskPart
EOF
}

wait_keypress()
{
	local _tmp

	_msg=$1
	if [ -n "${_msg}" ]
	then
		echo "${_msg}"
	fi

	_msg="Press ENTER to continue."
	read -p "${_msg}" _tmp
}

get_memory_disks_list()
{
	local _disks

	VAL=""
	if [ -n "${__FREENAS_DEBUG__}" ]
	then
		_disks=`mdconfig -l`
		VAL="${_disks}"
	fi

	export VAL
}

get_physical_disks_list()
{
	local _disks
	local _list
	local _d

	_list=""
	_disks=`sysctl -n kern.disks`
	for _d in ${_disks}
	do
		if echo "${_d}" | grep -vE '^cd' >/dev/null 2>&1
		then
			_list="${_list}${_d} "
		fi
	done

	VAL="${_list}"
	export VAL
}

get_media_description()
{
	local _media

	_media=$1
	VAL=""

	if [ -n "${_media}" ]
	then
		_description=`pc-sysinstall disk-list -c |grep "^${_media}"\
			|awk -F':' '{print $2}'|sed -E 's|.*<(.*)>.*$|\1|'`
		VAL="${_description}"
	fi

	export VAL
}

disk_is_mounted()
{
	local _disk
	local _dev
	local _res

	_res=0
	_disk=$1
	_dev="/dev/${_disk}"
	mount -v|grep -E "^${_dev}[sp][0-9]+" >/dev/null 2>&1
	_res=$?

	return ${_res}
}

menu_install()
{
	local _disklist
	local _tmpfile
	local _answer
	local _cdlist
	local _items
	local _cdrom
	local _disk
        local _image
        local _config_file
	local _desc
	local _list
	local _msg
	local _i

        _tmpfile="/tmp/msg"

        cat << EOD > "${_tmpfile}"
FreeNAS  installer for Flash device or HDD.

WARNING: There will be some limitations:
1. This will erase ALL partitions and data on the destination disk
2. You can't use your destination disk for sharing data

Installing on USB key is the preferred way:
It saves you an IDE, SATA or SCSI channel for more hard drives.

EOD

    _msg=`cat "${_tmpfile}"`
    rm -f "${_tmpfile}"


    dialog --title "FreeNAS installation" --yesno "${_msg}" 17 74
    if [ "$?" != "0" ]
    then
        exit 1
    fi

    get_physical_disks_list
    _disklist="${VAL}"

    get_memory_disks_list
    _disklist="${_disklist} ${VAL}"	

    _list=""
    _items=0
    for _disk in ${_disklist}
    do
        get_media_description "${_disk}"
        _desc="${VAL}"
        _list="${_list} ${_disk} '${_desc}'"
        _items=$((${_items} + 1))
    done

    _tmpfile="/tmp/answer"
    eval "dialog --title 'Choose destination media' \
          --menu 'Select media where FreeNAS OS should be installed.' \
          15 60 ${_items} ${_list}" 2>"${_tmpfile}"
    if [ "$?" != "0" ]; then
        exit 1
    fi

    _disk=`cat "${_tmpfile}"`
    rm -f "${_tmpfile}"

    if disk_is_mounted "${_disk}" ; then
        wait_keypress "The destination drive is already in use!"
        exit 1
    fi

    get_image_name
    _image="${VAL}"

    _config_file="/tmp/pc-sysinstall.cfg"

    #  _cdrom, _disk, _image, _config_file
    # we can now build a config file for pc-sysinstall
    build_config  ${_disk} ${_image} ${_config_file}

    # Run pc-sysinstall against the config generated

    # Hack #1
    export ROOTIMAGE=1
    # Hack #2
    ls /cdrom > /dev/null
    export LOGOUT=/var/log/freenas-install.log
    cp /dev/null $LOGOUT
    tail -F $LOGOUT &
    /rescue/pc-sysinstall -c ${_config_file}

    cat << EOD

FreeNAS has been successfully installed on ${_disk}.
Please remove the CDROM and reboot this machine.

EOD
    wait_keypress ""
    return 0
}

menu_null()
{
}

menu_reset()
{
}

menu_shell()
{
	eval /bin/sh
}

menu_reboot()
{
	dialog --yesno "Do you really want to reboot the system?" 5 46 no
	if [ "$?" = "0" ]
	then
		reboot >/dev/null
	fi
}

menu_shutdown()
{
	dialog --yesno "Do you really want to shutdown the system?" 5 46 no
	if [ "$?" = "0" ]
	then
		halt -p >/dev/null
	fi
}

menu()
{
	local _tmpfile="/tmp/answer"
	while :
	do
		local _number

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

main()
{
	menu;
}


main;
