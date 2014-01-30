
#!/bin/sh

set -e
set -x

my_cleanup()
{

    set +e
    if [ "x$md_mount" != "x" ] ; then
	umount "${NANO_OBJ}/_.mnt/"
	unset md_mount
    fi
    if [ "x$md_device" != "x" ] ; then
	mdconfig -d -u `echo $md_device | sed 's/[^0-9]//g'`
	unset md_device
    fi

}

on_exit()
{
    my_cleanup

}
trap on_exit EXIT

mydir=`dirname $0`
. "$mydir/make_install_fs.sh"

common_installfs "${NANO_OBJ}/_.isodir"

build_installfs  "${NANO_OBJ}/_.isodir"

	OUTPUT="${NANO_OBJ}/$NANO_NAME.install.img" # Output file of mkisofs
	USB_LABEL=${NANO_LABEL}INSTALL
	MKISOFS_CMD="/usr/local/bin/mkisofs -R -l -ldots -allow-lowercase \
			 -allow-multidot -hide boot.catalog -V ${CDROM_LABEL} -o ${OUTPUT} -no-emul-boot \
			 -b boot/cdboot ${STAGE_DIR}"

	cp -p ${AVATAR_ROOT}/build/files/loader.conf.bootusb ${STAGE_DIR}/boot/loader.conf
	sed -i "" 's/%USB_LABEL%/'${USB_LABEL}'/'  ${STAGE_DIR}/boot/loader.conf
	sed -i "" 's/%NANO_LABEL_LOWER%/'${NANO_LABEL_LOWER}'/'  ${STAGE_DIR}/boot/loader.conf
	cp -p ${AVATAR_ROOT}/build/files/mount.conf.cdrom ${STAGE_DIR}/.mount.conf

	rm -f "${OUTPUT}"
	dd if=/dev/zero "of=${OUTPUT}" bs=1m count=280
	md_device=`mdconfig -f "${OUTPUT}"`
	if [ $? != 0 ] ; then
	    echo mdconfig failed...
	    exit 1
	fi
	trap "" EXIT ; 
	md_path="/dev/$md_device"
	gpart create -s MBR "$md_device"
	gpart add -t freebsd "$md_device"
	gpart set -a active -i 1 "$md_device"
	gpart bootcode -b /boot/mbr "$md_device"

	gpart create -s BSD -n 20 "${md_device}s1"

	gpart add -t freebsd-ufs -s 270M "${md_device}s1"
	# make a spare for scratch space for debug/work.
	gpart add -t freebsd-ufs "${md_device}s1"

	gpart bootcode -b /boot/boot "${md_device}s1"

	fsdevice="${md_path}s1a"
	newfs -L "${USB_LABEL}" "$fsdevice"
	# make debug partition useful for putting hacks to the installer
	newfs "${md_path}s1b"
	md_mount="${NANO_OBJ}/_.mnt/"
	mount "$fsdevice" "$md_mount"
	tar -C  "${STAGE_DIR}" -cf - . | tar -C "$md_mount" -xvpf -
	trap "" EXIT ;
	my_cleanup

        ( cd $NANO_OBJ
          sha256_signature=`sha256 ${NANO_NAME}.install.img`
          echo "${sha256_signature}" > ${NANO_NAME}.install.img.sha256.txt
        )

	echo "Created ${OUTPUT}"
