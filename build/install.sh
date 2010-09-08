#!/bin/sh

__FREENAS_DEBUG__=1


get_product_name()
{
	local _product

	_product="FreeNAS"
	VAL="${_product}"

	export VAL
}

get_product_arch()
{
	local _arch

	_arch="amd64"
	VAL="${_arch}"

	export VAL
}

get_product_path()
{
	local _path

	_path="/home/jpaetzel/images"
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

	VAL="${_path}/${_product}-${_arch}-embedded.gz"
	export VAL
}

build_config()
{
        # build_config ${_install_type} ${_cdrom} ${_disk} ${_image}
        # ${_config_file}
        # Couple of issues here.
        # The mount point in the setting of image should match that
        # of the mount point used by install_mount_cd
        # There is magic used to determine what to do if
        # _install_type is set to 1

        local _install_type=$1
        local _cdrom=$2
        local _disk=$3
        local _image=$4
        local _config_file=$5

        if [ "$_install_type" = "1" ]; then
            cat << EOF > "${_config_file}"
# Added to stop pc-sysinstall from complaining
installMode=fresh
installInteractive=no
installType=FreeBSD
installMedium=dvd
packageType=tar

disk0=${_disk}
partition=image
image=/mnt/cdrom${_image}
rootimage=1
bootManager=bsd
commitDiskPart
EOF
        fi
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

get_cdrom_list()
{
	local _disks
	local _list
	local _d

	_list=""
	_disks=`sysctl -n kern.disks`
	for _d in ${_disks}
	do
		if echo "${_d}" | grep -E '^cd' >/dev/null >/dev/null 2>&1
		then
			_list="${_list}${_d} "
		fi
	done

	VAL="${_list}"
	export VAL
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
		_description=`pc-sysinstall disk-list -c -m|grep "^${_media}"\
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

install_mount_cd()
{
	local _cdrom
	local _mntpath

	echo "Mount CDROM."

	_cdrom=$1
	_mntpath="/mnt/cdrom"
	if [ ! -d "${_mntpath}" ]
	then
		mkdir -p "${_mntpath}"
		if [ "$?" != "0" ]
		then
			echo "Error: Failed to create directory '${_mntpath}'"
			return 1
		fi
	fi

	if [ -z "${__FREENAS_DEBUG__}" ]
	then
		mount_cd9660 "/dev/${_cdrom}" "${_mntpath}"
	else
		mount_nullfs "/home/jpaetzel/images/" "${_mntpath}"
	fi 

	if [ "$?" != "0" ]
	then
		echo "Error: Failed to mount device '${_cdrom}'!"
		rmdir "${_mntpath}"
		return 1
	fi

	return 0
}

install_unmount_cd()
{
	local _mntpath
	local _res

	echo "Unmount CDROM."

	_mntpath="/mnt/cdrom"
	umount "${_mntpath}"
	_res=$?

	rmdir "${_mntpath}"
	return ${_res}
}

do_install_1()
{
	local _disklist
	local _tmpfile
	local _answer
	local _cdlist
	local _items
	local _cdrom
	local _disk
        local _image
        local _install_type
        local _config_file
	local _desc
	local _list
	local _msg
	local _i

	_tmpfile="/tmp/msg"

	cat << EOD > "${_tmpfile}"
FreeNAS 'embedded' installer for Flash device or HDD.

- Create 1 partition for OS image
- Uses a RAM disk to limit read/write access to the device

WARNING: There will be some limitations:
1. This will erase ALL partitions and data on the destination disk
2. You can't use your destination disk for sharing data

Installing on USB key is the preferred way:
It saves you an IDE or SCSI channel for more hard drives.

EOD

	_msg=`cat "${_tmpfile}"`
	rm -f "${_tmpfile}"

	dialog --title "FreeNAS installation" --yesno "${_msg}" 17 74
	if [ "$?" != "0" ]
	then
		exit 1
	fi

	get_cdrom_list
	_cdlist="${VAL}"
	if [ -z "${_cdlist}" ]
	then
		wait_keypress "Failed to detect any CDROM."
		exit 1
	fi

	_list=""
	for _cd in ${_cdlist}
	do
		get_media_description "${_cd}"
		_desc="${VAL}"
		_list="${_list} ${_cd} '${_desc}'"
	done

	_tmpfile="/tmp/answer"
	eval "dialog --title 'Choose installation media' \
		--menu 'Select CD/DVD drive for installation.' \
		10 60 6 ${_list}" 2>"${_tmpfile}"
	if [ "$?" != "0" ]
	then
		exit 1
	fi

	### XXXX
	_cdrom=`cat "${_tmpfile}"`
	rm -f "${_tmpfile}"

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
	if [ "$?" != "0" ]
	then
		exit 1
	fi

	### XXXX
	_disk=`cat "${_tmpfile}"`
	rm -f "${_tmpfile}"

	if disk_is_mounted "${_disk}"
	then
		wait_keypress "The destination drive is already in use!"
		exit 1
	fi

        get_image_name
        _image="${VAL}"

        # Can we avoid magic?  We need a way to tell build_config
        # how we are going to lay out the disk, for the OS,
        # swap, data.  For the moment 1 is defined as use the 
        # whole device for a single slice that contains the image

        _install_type="1"
        _config_file="/tmp/pc-sysinstall.cfg"

        # _install_type, _cdrom, _disk, _image, _config_file
        # we can now build a config file for pc-sysinstall
        build_config ${_install_type} ${_cdrom} ${_disk} \
                     ${_image} ${_config_file}

        install_mount_cd ${_cdrom}
        # Run pc-sysinstall against the config generated
        ../pc-sysinstall/pc-sysinstall -c ${_config_file}
        install_unmount_cd

	cat << EOD > "${_tmpfile}"

FreeNAS has been installed on ${_disk}.
You can now remove the CDROM and reboot the PC.
EOD

	_msg=`cat "${_tmpfile}"`
	rm -f "${_tmpfile}"

	wait_keypress "${_msg}"
	return 0
}

menu_null()
{
}

menu_reset()
{
}

menu_ping()
{
	local _tmpfile
	local _host
	local _res

	_tmpfile="/tmp/answer"
	trap "rm -f ${_tmpfile}" 0 1 2 5 15

	dialog --inputbox "Enter a host name or IP address." 8 50 2>"${_tmpfile}"
	_res=$?

	_host=`cat "${_tmpfile}"`
	if [ -n "${_host}" ] && [ "${_res}" = "0" ]
	then
		:
	fi
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

menu_install()
{
	local _number
	local _tmpfile

	_tmpfile="/tmp/answer"

	dialog --clear --title "Install & Upgrade" --menu "" 12 73 6 \
	"1" "Install 'embedded' OS on HDD/Flash/USB" \
	"2" "Install 'embedded' OS on HDD/Flash/USB + DATA + SWAP partition" \
	"3" "Install 'full' OS on HDD + DATA + SWAP partition" \
	"4" "Upgrade 'embedded' OS from CDROM" \
	"5" "Upgrade 'full' OS from CDROM" \
	"6" "Upgrade and convert 'full' OS to 'embedded'" 2> "${_tmpfile}"

	if [ "$?" != "0" ]
	then
		return 1
	fi

	_number=`cat "${_tmpfile}"`
	case "${_number}" in
		1) do_install_1 ;;
		2) ;;
		3) ;;
		4) ;;
		5) ;;
		6) ;;
	esac

	return 0
}


menu()
{
	while :
	do
		local _number

		echo " "
		echo " "
		echo "Console setup"
		echo "-------------"
		echo "1) Assign interfaces"
		echo "2) Set LAN IP address"
		echo "3) Reset WebGUI password"
		echo "4) Reset to factory defaults"
		echo "5) Ping host"
		echo "6) Shell"
		echo "7) Reboot system"
		echo "8) Shutdown System"
		echo "9) Install/Upgrade to hard drive/flash device, etc."
		echo " "

		read -p "Enter a number: " _number

		case "${_number}" in
			1) menu_null ;;
			2) menu_null ;;
			3) menu_null ;;
			4) menu_null ;;
			5) menu_ping ;;
			6) menu_shell ;;
			7) menu_reboot ;;
			8) menu_shutdown ;;
			9) menu_install ;;
		esac

	done
}


main()
{
	menu;
}


main;
