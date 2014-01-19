#!/bin/sh
#
#  PXE Configuration script
#
#  Preparation
#  ===========
#  (1) Read this document for how to set up a PXE boot
#      environment with an NFS root:
#         http://www.freebsd.org/doc/en/books/handbook/network-pxe-nfs.html
#
#  (2) Create a directory /usr/jails/pxeserver/  and install your NFS root into that directory.
#  (3) Create a directory /usr/jails/pxeserver/images and upload your ISO image into that directory. 
#  (4) Configure /etc/inetd.conf and /usr/local/etc/dhcpd.conf as specified in (1).
#
#  Description
#  ===========
#  This script will look in /usr/jails/pxeserver/images/ and present
#  a menu listing the available ISO images.  When the user selects an ISO
#  image, the script extracts the contents of ISO into a special directory
#  which can be NFS exported.  This NFS directory can be used
#  as an NFS root file system during PXE boot. 
#

# Setup a semi-sane environment
PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
export PATH
HOME=/root
export HOME
TERM=${TERM:-cons25}
export TERM

IMAGES_DIR=/usr/jails/pxeserver/images
PXE_HOST=10.5.0.24
NFS_ROOT_PATH=/usr/jails/pxeserver/images/boot_dir
TEST_HOST=10.5.0.24
TEST_NFS_MOUNT=/usr/jails/pxeserver

wait_keypress()
{
    local _tmp
    read -p "Press ENTER to continue." _tmp
}

menu_shell()
{
    /bin/sh
}

get_images()
{
    (
        local images
        local image
 
        cd $IMAGES_DIR
        for image in `ls -1t *.iso 2> /dev/null`; do
            if [ -f $image ]; then
                 images="$images $image"
            fi
        done
        echo "$images"
    )
}

build_choices_from_list()
{
    local item
    local list
    local i

    i=0
    for item in $@; do
        i=$(($i+1))
        list="$list $i $item"
    done

    echo "$list"
}

get_current_boot_image()
{
    (
        cd $IMAGES_DIR
        if [ -n selected_boot_image ]; then
            echo $(basename $(realpath selected_boot_image))
        else
            echo "" 
        fi
    )
}

get_choice_from_list()
{
    local choice
    local value

    choice=$1
    value=""

    shift

    while [ -n "$1" ] ; do
        if [ "$1" = "$choice" ]; then
            value="$2"
        fi
        shift 2 
    done

    echo $value 
}

prepare_boot_image()
{
    local boot_image=$1

    (   set -x
        cd $IMAGES_DIR
        ln -s -f $boot_image selected_boot_image
        rm -fr boot_dir
        mkdir -p boot_dir 
        bsdtar -x -f $boot_image -C boot_dir
        mkdir -p boot_dir/etc
        #echo "$PXE_HOST:$NFS_ROOT_PATH       /     nfs    ro   0   0" > boot_dir/etc/fstab  
        sed -i "" '/boot_cdrom/d' boot_dir/boot/loader.conf 
        sed -i "" '/cam_boot_delay/d' boot_dir/boot/loader.conf
        echo "test.nfs_mount=\"$TEST_HOST:$TEST_NFS_MOUNT\"" >> boot_dir/boot/loader.conf
        echo "test.script=\"/tests/run-tests.sh\"" >> boot_dir/boot/loader.conf
        echo "test.run_tests_on_boot=\"yes\"" >> boot_dir/boot/loader.conf
        set +x
    ) 
}

main()
{
    local _tmpfile="/tmp/answer"
    local _number
    local images
    local list
    local current_boot_choice
    local selected_image

    images=$(get_images)
    list=$(build_choices_from_list $images)

    if [ -z "$list" ]; then
        echo "No images in $IMAGES_DIR"
        exit 1
    fi

    while :; do
        current_boot_choice=$(get_current_boot_image)
        
        dialog --clear --no-ok --no-cancel --title "PXE Configuration Setup" --backtitle "Current boot image is: $current_boot_choice" --menu "Select boot image:" 12 73 10 \
            $list "x" "Exit" \
            2> "${_tmpfile}"
        _number=`cat "${_tmpfile}"`
        if [ -z "$_number" -o "$_number" = "x" ]; then
           exit 0
        fi

        selected_image=$(get_choice_from_list $_number $list)
        prepare_boot_image $selected_image
    done
}

main
