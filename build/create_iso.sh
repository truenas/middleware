#!/bin/sh

set -e

# This script creates a bootable LiveCD ISO from a nanobsd image for FreeNAS

main()
{
	export AVATAR_ROOT=$(realpath "$(dirname "$0")/..")
	. "$AVATAR_ROOT/build/nano_env"
	. "$AVATAR_ROOT/build/functions.sh"

	if [ -z "NANO_LABEL" ] ; then
		echo NANO_LABEL unset
		exit 2
	fi
	if [ -z "VERSION" ] ; then
		echo VERSION unset
		exit 2
	fi

	requires_root

	TEMP_IMGFILE="${NANO_OBJ}/_.imgfile" # Scratch file for image

	INSTALLER_FILES="$AVATAR_ROOT/build/nanobsd-cfg/Installer"
	AVATAR_CONF="$NANO_OBJ/_.w/etc/avatar.conf"

	# Various mount points needed to build the CD, adjust to taste
	ISODIR="${NANO_OBJ}/_.isodir" # Directory ISO is rolled from
	INSTALLUFSDIR="${NANO_OBJ}/_.instufs" # Scratch mountpoint where the image will be dissected

	OUTPUT="${NANO_OBJ}/$NANO_NAME.iso" # Output file of mkisofs

	CDROM_LABEL=${NANO_LABEL}_INSTALL
	#MKISOFS_CMD="/usr/local/bin/mkisofs -R -l -ldots -allow-lowercase \
	#		 -allow-multidot -hide boot.catalog -V ${CDROM_LABEL} -o ${OUTPUT} -no-emul-boot \
	#		 -b boot/cdboot ${ISODIR}"
	MKISOFS_CMD="/usr/local/bin/grub-mkrescue -o ${OUTPUT} ${ISODIR} -- -volid ${CDROM_LABEL}"

	#if ! command -v mkisofs >/dev/null 2>&1; then
	#	error "mkisofs not available.  Please install the sysutils/cdrtools port."
	#fi

	cleanup

	cd "$AVATAR_ROOT"


	mkdir -p ${ISODIR}/data
	mkdir -p ${ISODIR}/dev
	mkdir -p ${ISODIR}/.mount
	mkdir -p ${ISODIR}/mnt
	mkdir -p ${ISODIR}/tmp
	mkdir -p ${ISODIR}/boot/grub

	# Create the install ISO based on contents from the installworld tree
	mkdir -p ${INSTALLUFSDIR}
	tar -cf - -C ${NANO_OBJ}/_.w --exclude local --exclude workdir . | tar -xf - -C ${INSTALLUFSDIR}

	# copy /rescue and /boot from the image to the iso
	tar -c -f - -C ${NANO_OBJ}/_.w --exclude boot/kernel-debug boot | tar -x -f - -C ${ISODIR}

	(cd build/pc-sysinstall && make install DESTDIR=${INSTALLUFSDIR} NO_MAN=t)
	rm -rf ${INSTALLUFSDIR}/usr/local
	rm -rf ${INSTALLUFSDIR}/usr/include
	rm -rf ${INSTALLUFSDIR}/boot
	rm -f ${INSTALLUFSDIR}/bin/* ${INSTALLUFSDIR}/sbin/*
	rm -f ${INSTALLUFSDIR}/usr/bin/* ${INSTALLUFSDIR}/usr/sbin/*
	mkdir -p ${INSTALLUFSDIR}/usr/local/pre-install
	mkdir -p ${INSTALLUFSDIR}/usr/local/firmware
	mkdir -p ${INSTALLUFSDIR}/usr/local/install
	mkdir -p ${INSTALLUFSDIR}/usr/local/sbin

	# Copy python and sqlite3 to the installation directory
	set -x
	echo " * * * * * * * * "
	( cd ${NANO_OBJ}/_.w ; tar -cf - ./usr/local/lib/*python* ./usr/local/bin/python* ./usr/local/lib/libsqlite* ./usr/local/lib/libssl* ./usr/local/lib/libcrypto* /usr/local/lib/libffi*) |
	tar -xf - -C ${INSTALLUFSDIR}
	# Copy the installation scripts and modules as well
	tar -C ${NANO_OBJ}/_.pkgtools -cf - ./usr/local/lib ./usr/local/bin/freenas-install | tar -C ${INSTALLUFSDIR} -xf -
        # And prune that out a bit -- these are just some big ones
        rm -rf ${INSTALLUFSDIR}/usr/local/lib/python*/test
        for pkg in pysphere samba django south Crypto lxml _xmlplus
        do
            rm -rf ${INSTALLUFSDIR}/usr/local/lib/python*/site-packages/${pkg}
        done
        rm -rf ${INSTALLUFSDIR}/var/db/pkg
        rm -rf ${INSTALLUFSDIR}/conf
        rm -rf ${INSTALLUFSDIR}/usr/share/man
        rm -rf ${INSTALLUFSDIR}/usr/share/groff_font
        rm -rf ${INSTALLUFSDIR}/usr/share/locale
        rm -rf ${INSTALLUFSDIR}/usr/share/misc
        rm -rf ${INSTALLUFSDIR}/usr/share/zoneinfo
        find -x ${INSTALLUFSDIR} \( -name '*.a' -o -name '*.pyc' \) -type f -print0 | xargs -0 rm -f

	set +x
# SEF
# Build packages here.

	if [ -d ${NANO_OBJ}/_.packages/Packages ]; then
	    mkdir -p ${NANO_OBJ}/_.isodir/${NANO_LABEL}
	    cp -R ${NANO_OBJ}/_.packages/Packages ${NANO_OBJ}/_.isodir/${NANO_LABEL}
	    cp ${NANO_OBJ}/_.packages/${NANO_LABEL}-MANIFEST ${NANO_OBJ}/_.isodir/${NANO_LABEL}-MANIFEST
	else
		echo "Hey, where are the install filess?"
	fi
	if [ -d ${NANO_OBJ}/_.data ]; then
		mkdir -p ${NANO_OBJ}/_.instufs/data
		tar -C ${NANO_OBJ}/_.data -cf - . |
			tar -C ${NANO_OBJ}/_.instufs/data -xpf -
	fi

	cp -p ${AVATAR_ROOT}/build/files/install.sh ${INSTALLUFSDIR}/etc
	if [ -f ${AVATAR_ROOT}/install.conf ]; then
	    cp ${AVATAR_ROOT}/install.conf ${INSTALLUFSDIR}/etc/install.conf
	fi
	if is_truenas ; then
		cp -p ${TRUENAS_COMPONENTS_ROOT}/build/files/install_sata_dom.sh \
			${INSTALLUFSDIR}/etc
		cp -Rp ${TRUENAS_COMPONENTS_ROOT}/nanobsd/Installer/install/ \
			${INSTALLUFSDIR}/usr/local/install/
	fi
	cp -p ${AVATAR_ROOT}/build/files/rc ${INSTALLUFSDIR}/etc

	cp "$AVATAR_CONF" ${INSTALLUFSDIR}/etc/
	mkdir -p ${INSTALLUFSDIR}/usr/local/
	tar -cf - -C${INSTALLER_FILES} --exclude .svn . | tar -xpf - -C ${INSTALLUFSDIR}/usr/local/

	mkdir -p ${INSTALLUFSDIR}/.mount
	mkdir -p ${INSTALLUFSDIR}/cdrom
	mkdir -p ${INSTALLUFSDIR}/conf/default/etc
	mkdir -p ${INSTALLUFSDIR}/conf/default/tmp
	mkdir -p ${INSTALLUFSDIR}/conf/default/var
	mkdir -p ${INSTALLUFSDIR}/tank

	# XXX: tied too much to the host system to be of value in the
	# installer code.
	rm -f "$INSTALLUFSDIR/etc/rc.conf.local"
	rm -f "$INSTALLUFSDIR/conf/base/etc/rc.conf.local"
	rm -f $INSTALLUFSDIR/etc/fstab
	rm -f $INSTALLUFSDIR/conf/default/etc/remount

	# If it exists in /rescue, create a symlink in one of the
	# /bin directories for compatibility with scripts.
	#
	ln -s /rescue/[ ${INSTALLUFSDIR}/bin/[
	ln -s /rescue/atacontrol ${INSTALLUFSDIR}/sbin/atacontrol
	ln -s /rescue/badsect ${INSTALLUFSDIR}/sbin/badsect
	ln -s /rescue/bsdlabel ${INSTALLUFSDIR}/sbin/bsdlabel
	ln -s /rescue/bunzip2 ${INSTALLUFSDIR}/usr/bin/bunzip2
	ln -s /rescue/bzcat ${INSTALLUFSDIR}/usr/bin/bzcat
	ln -s /rescue/bzip2 ${INSTALLUFSDIR}/usr/bin/bzip2
	ln -s /rescue/camcontrol ${INSTALLUFSDIR}/sbin/camcontrol
	ln -s /rescue/cat ${INSTALLUFSDIR}/bin/cat
	ln -s /rescue/ccdconfig ${INSTALLUFSDIR}/sbin/ccdconfig
	ln -s /rescue/chflags ${INSTALLUFSDIR}/bin/chflags
	ln -s /rescue/chgrp ${INSTALLUFSDIR}/usr/bin/chgrp
	ln -s /rescue/chio ${INSTALLUFSDIR}/bin/chio
	ln -s /rescue/chmod ${INSTALLUFSDIR}/bin/chmod
	ln -s /rescue/chown ${INSTALLUFSDIR}/usr/sbin/chown
	ln -s /rescue/chroot ${INSTALLUFSDIR}/usr/sbin/chroot
	ln -s /rescue/clri ${INSTALLUFSDIR}/sbin/clri
	ln -s /rescue/cp ${INSTALLUFSDIR}/bin/cp
	ln -s /rescue/csh ${INSTALLUFSDIR}/bin/csh
	ln -s /rescue/date ${INSTALLUFSDIR}/bin/date
	ln -s /rescue/dd ${INSTALLUFSDIR}/bin/dd
	ln -s /rescue/devfs ${INSTALLUFSDIR}/sbin/devfs
	ln -s /rescue/df ${INSTALLUFSDIR}/bin/df
	ln -s /rescue/dhclient ${INSTALLUFSDIR}/sbin/dhclient
	ln -s /rescue/dhclient-script ${INSTALLUFSDIR}/sbin/dhclient-script
	ln -s /rescue/disklabel ${INSTALLUFSDIR}/sbin/disklabel
	ln -s /rescue/dmesg ${INSTALLUFSDIR}/sbin/dmesg
	ln -s /rescue/dump ${INSTALLUFSDIR}/sbin/dump
	ln -s /rescue/dumpfs ${INSTALLUFSDIR}/sbin/dumpfs
	ln -s /rescue/dumpon ${INSTALLUFSDIR}/sbin/dumpon
	ln -s /rescue/echo ${INSTALLUFSDIR}/bin/echo
	ln -s /rescue/ed ${INSTALLUFSDIR}/bin/ed
	ln -s /rescue/ex ${INSTALLUFSDIR}/usr/bin/ex
	ln -s /rescue/expr ${INSTALLUFSDIR}/bin/expr
	ln -s /rescue/fastboot ${INSTALLUFSDIR}/sbin/fastboot
	ln -s /rescue/fasthalt ${INSTALLUFSDIR}/sbin/fasthalt
	ln -s /rescue/fdisk ${INSTALLUFSDIR}/sbin/fdisk
	ln -s /rescue/fsck ${INSTALLUFSDIR}/sbin/fsck
	ln -s /rescue/fsck_4.2bsd ${INSTALLUFSDIR}/sbin/fsck_4.2bsd
	ln -s /rescue/fsck_ffs ${INSTALLUFSDIR}/sbin/fsck_ffs
	ln -s /rescue/fsck_msdosfs ${INSTALLUFSDIR}/sbin/fsck_msdosfs
	ln -s /rescue/fsck_ufs ${INSTALLUFSDIR}/sbin/fsck_ufs
	ln -s /rescue/fsdb ${INSTALLUFSDIR}/sbin/fsdb
	ln -s /rescue/fsirand ${INSTALLUFSDIR}/sbin/fsirand
	ln -s /rescue/gbde ${INSTALLUFSDIR}/sbin/gbde
	ln -s /rescue/getfacl ${INSTALLUFSDIR}/bin/getfacl
	ln -s /rescue/groups ${INSTALLUFSDIR}/usr/bin/groups
	ln -s /rescue/gunzip ${INSTALLUFSDIR}/usr/bin/gunzip
	ln -s /rescue/gzcat ${INSTALLUFSDIR}/usr/bin/gzcat
	ln -s /rescue/gzip ${INSTALLUFSDIR}/usr/bin/gzip
	ln -s /rescue/halt ${INSTALLUFSDIR}/sbin/halt
	ln -s /rescue/head ${INSTALLUFSDIR}/usr/bin/head
	ln -s /rescue/hostname ${INSTALLUFSDIR}/bin/hostname
	ln -s /rescue/id ${INSTALLUFSDIR}/usr/bin/id
	ln -s /rescue/ifconfig ${INSTALLUFSDIR}/sbin/ifconfig
	ln -s /rescue/init ${INSTALLUFSDIR}/sbin/init
	ln -s /rescue/kenv ${INSTALLUFSDIR}/bin/kenv
	ln -s /rescue/kill ${INSTALLUFSDIR}/bin/kill
	ln -s /rescue/kldconfig ${INSTALLUFSDIR}/sbin/kldconfig
	ln -s /rescue/kldload ${INSTALLUFSDIR}/sbin/kldload
	ln -s /rescue/kldstat ${INSTALLUFSDIR}/sbin/kldstat
	ln -s /rescue/kldunload ${INSTALLUFSDIR}/sbin/kldunload
	ln -s /rescue/ldconfig ${INSTALLUFSDIR}/sbin/ldconfig
	ln -s /rescue/less ${INSTALLUFSDIR}/usr/bin/less
	ln -s /rescue/link ${INSTALLUFSDIR}/bin/link
	ln -s /rescue/ln ${INSTALLUFSDIR}/bin/ln
	ln -s /rescue/ls ${INSTALLUFSDIR}/bin/ls
	ln -s /rescue/lzcat ${INSTALLUFSDIR}/usr/bin/lzcat
	ln -s /rescue/lzma ${INSTALLUFSDIR}/usr/bin/lzma
	ln -s /rescue/md5 ${INSTALLUFSDIR}/sbin/md5
	ln -s /rescue/mdconfig ${INSTALLUFSDIR}/sbin/mdconfig
	ln -s /rescue/mdmfs ${INSTALLUFSDIR}/sbin/mdmfs
	ln -s /rescue/mkdir ${INSTALLUFSDIR}/bin/mkdir
	ln -s /rescue/mknod ${INSTALLUFSDIR}/sbin/mknod
	ln -s /rescue/more ${INSTALLUFSDIR}/usr/bin/more
	ln -s /rescue/mount ${INSTALLUFSDIR}/sbin/mount
	ln -s /rescue/mount_cd9660 ${INSTALLUFSDIR}/sbin/mount_cd9660
	ln -s /rescue/mount_msdosfs ${INSTALLUFSDIR}/sbin/mount_msdosfs
	ln -s /rescue/mount_nfs ${INSTALLUFSDIR}/sbin/mount_nfs
	ln -s /rescue/mount_nullfs ${INSTALLUFSDIR}/sbin/mount_nullfs
	ln -s /rescue/mount_udf ${INSTALLUFSDIR}/sbin/mount_udf
	ln -s /rescue/mount_unionfs ${INSTALLUFSDIR}/sbin/mount_unionfs
	ln -s /rescue/mt ${INSTALLUFSDIR}/usr/bin/mt
	ln -s /rescue/mv ${INSTALLUFSDIR}/bin/mv
	ln -s /rescue/nc ${INSTALLUFSDIR}/usr/bin/nc
	ln -s /rescue/newfs ${INSTALLUFSDIR}/sbin/newfs
	ln -s /rescue/newfs_msdos ${INSTALLUFSDIR}/sbin/newfs_msdos
	ln -s /rescue/nextboot ${INSTALLUFSDIR}/sbin/nextboot
	ln -s /rescue/nos-tun ${INSTALLUFSDIR}/sbin/nos-tun
	ln -s /rescue/pc-sysinstall ${INSTALLUFSDIR}/usr/sbin/pc-sysinstall
	ln -s /rescue/pgrep ${INSTALLUFSDIR}/bin/pgrep
	ln -s /rescue/ping ${INSTALLUFSDIR}/sbin/ping
	ln -s /rescue/ping6 ${INSTALLUFSDIR}/sbin/ping6
	ln -s /rescue/pkill ${INSTALLUFSDIR}/bin/pkill
	ln -s /rescue/ps ${INSTALLUFSDIR}/bin/ps
	ln -s /rescue/pwd ${INSTALLUFSDIR}/bin/pwd
	ln -s /rescue/rcorder ${INSTALLUFSDIR}/sbin/rcorder
	ln -s /rescue/rdump ${INSTALLUFSDIR}/sbin/rdump
	ln -s /rescue/realpath ${INSTALLUFSDIR}/bin/realpath
	ln -s /rescue/reboot ${INSTALLUFSDIR}/sbin/reboot
	ln -s /rescue/red ${INSTALLUFSDIR}/bin/red
	ln -s /rescue/restore ${INSTALLUFSDIR}/sbin/restore
	ln -s /rescue/rm ${INSTALLUFSDIR}/bin/rm
	ln -s /rescue/rmdir ${INSTALLUFSDIR}/bin/rmdir
	ln -s /rescue/route ${INSTALLUFSDIR}/sbin/route
	ln -s /rescue/routed ${INSTALLUFSDIR}/sbin/routed
	ln -s /rescue/rrestore ${INSTALLUFSDIR}/sbin/rrestore
	ln -s /rescue/rtquery ${INSTALLUFSDIR}/sbin/rtquery
	ln -s /rescue/rtsol ${INSTALLUFSDIR}/sbin/rtsol
	ln -s /rescue/savecore ${INSTALLUFSDIR}/sbin/savecore
	ln -s /rescue/setfacl ${INSTALLUFSDIR}/bin/setfacl
	ln -s /rescue/sh ${INSTALLUFSDIR}/bin/sh
	ln -s /rescue/spppcontrol ${INSTALLUFSDIR}/sbin/spppcontrol
	ln -s /rescue/stty ${INSTALLUFSDIR}/bin/stty
	ln -s /rescue/swapon ${INSTALLUFSDIR}/sbin/swapon
	ln -s /rescue/sync ${INSTALLUFSDIR}/bin/sync
	ln -s /rescue/sysctl ${INSTALLUFSDIR}/sbin/sysctl
	ln -s /rescue/tail ${INSTALLUFSDIR}/usr/bin/tail
	ln -s /rescue/tar ${INSTALLUFSDIR}/usr/bin/tar
	ln -s /rescue/tcsh ${INSTALLUFSDIR}/bin/tcsh
	ln -s /rescue/tee ${INSTALLUFSDIR}/usr/bin/tee
	ln -s /rescue/test ${INSTALLUFSDIR}/bin/test
	ln -s /rescue/tunefs ${INSTALLUFSDIR}/sbin/tunefs
	ln -s /rescue/umount ${INSTALLUFSDIR}/sbin/umount
	ln -s /rescue/unlink ${INSTALLUFSDIR}/bin/unlink
	ln -s /rescue/unlzma ${INSTALLUFSDIR}/usr/bin/unlzma
	ln -s /rescue/unxz ${INSTALLUFSDIR}/usr/bin/unxz
	ln -s /rescue/vi ${INSTALLUFSDIR}/usr/bin/vi
	ln -s /rescue/whoami ${INSTALLUFSDIR}/usr/bin/whoami
	ln -s /rescue/xz ${INSTALLUFSDIR}/usr/bin/xz
	ln -s /rescue/xzcat ${INSTALLUFSDIR}/usr/bin/xzcat
	ln -s /rescue/zcat ${INSTALLUFSDIR}/usr/bin/zcat
	ln -s /rescue/zfs ${INSTALLUFSDIR}/sbin/zfs
	ln -s /rescue/zpool ${INSTALLUFSDIR}/sbin/zpool

	# Create additional symlinks
	ln -s /bin/pgrep ${INSTALLUFSDIR}/usr/bin/pgrep
	ln -s /bin/pkill ${INSTALLUFSDIR}/usr/bin/pkill
	ln -s /.mount/boot ${INSTALLUFSDIR}/boot

	# Copy in binaries needed on install CD-ROM
	cp -p ${NANO_OBJ}/_.w/bin/sleep ${INSTALLUFSDIR}/bin/sleep
	cp -p ${NANO_OBJ}/_.w/usr/bin/dialog ${INSTALLUFSDIR}/usr/bin/dialog
	cp -p ${NANO_OBJ}/_.w/usr/bin/dirname ${INSTALLUFSDIR}/usr/bin/dirname
	cp -p ${NANO_OBJ}/_.w/usr/bin/awk ${INSTALLUFSDIR}/usr/bin/awk
	cp -p ${NANO_OBJ}/_.w/usr/bin/cut ${INSTALLUFSDIR}/usr/bin/cut
	cp -p ${NANO_OBJ}/_.w/usr/bin/cmp ${INSTALLUFSDIR}/usr/bin/cmp
	cp -p ${NANO_OBJ}/_.w/usr/bin/find ${INSTALLUFSDIR}/usr/bin/find
	cp -p ${NANO_OBJ}/_.w/usr/bin/grep ${INSTALLUFSDIR}/usr/bin/grep
	cp -p ${NANO_OBJ}/_.w/usr/bin/logger ${INSTALLUFSDIR}/usr/bin/logger
	cp -p ${NANO_OBJ}/_.w/usr/bin/mkfifo ${INSTALLUFSDIR}/usr/bin/mkfifo
	cp -p ${NANO_OBJ}/_.w/usr/bin/mktemp ${INSTALLUFSDIR}/usr/bin/mktemp
	cp -p ${NANO_OBJ}/_.w/usr/bin/sed ${INSTALLUFSDIR}/usr/bin/sed
	cp -p ${NANO_OBJ}/_.w/usr/bin/sort ${INSTALLUFSDIR}/usr/bin/sort
	cp -p ${NANO_OBJ}/_.w/usr/bin/tr ${INSTALLUFSDIR}/usr/bin/tr
	cp -p ${NANO_OBJ}/_.w/usr/bin/uname ${INSTALLUFSDIR}/usr/bin/uname
	cp -p ${NANO_OBJ}/_.w/usr/bin/xargs ${INSTALLUFSDIR}/usr/bin/xargs
	cp -p ${NANO_OBJ}/_.w/usr/sbin/diskinfo ${INSTALLUFSDIR}/usr/sbin/diskinfo
	cp -p ${NANO_OBJ}/_.w/usr/sbin/vidcontrol ${INSTALLUFSDIR}/usr/sbin/vidcontrol
	cp -p ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/geom
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/gcache
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/gconcat
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/geli
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/gjournal
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/glabel
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/gmirror
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/gmountver
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/gmultipath
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/gnop
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/gpart
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/graid
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/graid3
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/gsched
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/gshsec
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/gstripe
	ln ${NANO_OBJ}/_.w/sbin/geom ${INSTALLUFSDIR}/sbin/gvirstor

	# The presence of /etc/diskless will trigger /etc/rc to run /etc/rc.initdiskless.
	touch ${INSTALLUFSDIR}/etc/diskless

	# Copy /etc to /conf/default/etc and /var to /conf/default/var.
	# The /etc/rc.initdiskless script will create memory file systems and copy these directories
	# into those memory file systems.
	tar -c -f - -C ${INSTALLUFSDIR}/etc . | tar -x -p -f - -C ${INSTALLUFSDIR}/conf/default/etc
	tar -c -f - -C ${INSTALLUFSDIR}/var . | tar -x -p -f - -C ${INSTALLUFSDIR}/conf/default/var

	# Compress what's left of the image after mangling it
	makefs -b 10%  ${TEMP_IMGFILE} ${INSTALLUFSDIR}
	mkuzip -o ${ISODIR}/data/base.ufs.uzip ${TEMP_IMGFILE}

	cp -p ${AVATAR_ROOT}/build/files/loader.conf.cdrom ${ISODIR}/boot/loader.conf
	cp -p ${AVATAR_ROOT}/build/files/grub.cfg.cdrom ${ISODIR}/boot/grub/grub.cfg
	sed -i "" 's/%CDROM_LABEL%/'${CDROM_LABEL}'/'  ${ISODIR}/boot/loader.conf
	sed -i "" 's/%CDROM_LABEL%/'${CDROM_LABEL}'/'  ${ISODIR}/boot/grub/grub.cfg
	sed -i "" 's/%NANO_LABEL%/'${NANO_LABEL}'/' ${ISODIR}/boot/grub/grub.cfg
	sed -i "" 's/%NANO_LABEL_LOWER%/'${NANO_LABEL_LOWER}'/'  ${ISODIR}/boot/loader.conf
	cp -p ${AVATAR_ROOT}/build/files/mount.conf.cdrom ${ISODIR}/.mount.conf

	eval ${MKISOFS_CMD}
        ( cd $NANO_OBJ
          sha256_signature=`sha256 ${NANO_NAME}.iso`
          echo "${sha256_signature}" > ${NANO_NAME}.iso.sha256.txt
        )

	echo "Created ${OUTPUT}"
}

cleanup()
{
	# Clean up directories used to create the liveCD
	rm -Rf "$ISODIR" "$INSTALLUFSDIR"
}

main
