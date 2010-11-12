#!/bin/sh -x

# This script creates a bootable LiveCD iso from a nanobsd image

root=$(pwd)
: ${FREENAS_ARCH=$(uname -p)}
export FREENAS_ARCH
export NANO_OBJ=${root}/obj.${FREENAS_ARCH}
: ${REVISION=`svnversion ${root} | tr -d M`}
export NANO_NAME="FreeNAS-8r${REVISION}-${FREENAS_ARCH}"
export NANO_IMGNAME="${NANO_NAME}.full"

main()
{
    # This script must be run as root
    if ! [ $(whoami) = "root" ]; then
        echo "This script must be run by root"
        exit
    fi

    # Paths that may need altering on the build system
    IMGFILE="${NANO_OBJ}/$NANO_IMGNAME"
    TEMP_IMGFILE="${NANO_OBJ}/_.imgfile" # Scratch file for image
    ETC_FILES="$root/build/files"

    # Various mount points needed to build the CD, adjust to taste
    STAGEDIR="${NANO_OBJ}/_.stage" # Scratch location for making filesystem image
    ISODIR="${NANO_OBJ}/_.isodir" # Directory ISO is rolled from
    INSTALLUFSDIR="${NANO_OBJ}/_.instufs" # Scratch mountpoint where the image will be dissected

    OUTPUT="${NANO_OBJ}/$NANO_IMGNAME.iso" # Output file of mkisofs

    # A command forged by the gods themselves, change at your own risk
    MKISOFS_CMD="/usr/local/bin/mkisofs -R -l -ldots -allow-lowercase \
                 -allow-multidot -hide boot.catalog -o ${OUTPUT} -no-emul-boot \
                 -b boot/cdboot ${ISODIR}"

    cleanup

    mkdir -p ${STAGEDIR}/dev
    mkdir -p ${ISODIR}/data

    # Create a quick and dirty nano image from the world tree
    mkdir -p ${INSTALLUFSDIR}
    tar -cf - -C ${NANO_OBJ}/_.w --exclude local . | tar -xvf - -C ${INSTALLUFSDIR}
    
    # copy /rescue and /boot from the image to the iso
    tar -cf - -C ${INSTALLUFSDIR} rescue | tar -xvf - -C ${STAGEDIR}
    tar -cf - -C ${INSTALLUFSDIR} boot | tar -xvf - -C ${ISODIR}
    xz --compress -9 < ${IMGFILE} > ${ISODIR}/FreeNAS-${FREENAS_ARCH}-embedded.xz

    echo "#/dev/md0 / ufs ro 0 0" > ${INSTALLUFSDIR}/etc/fstab
    echo 'root_rw_mount="NO"' >> ${INSTALLUFSDIR}/etc/rc.conf
    sed -i "" -e '/^sshd/d;/^light/d;/^ntpd/d' ${INSTALLUFSDIR}/etc/rc.conf
    echo 'cron_enable="NO"' >> ${INSTALLUFSDIR}/etc/rc.conf
    echo 'syslogd_enable="NO"' >> ${INSTALLUFSDIR}/etc/rc.conf
    echo 'inetd_enable="NO"' >> ${INSTALLUFSDIR}/etc/rc.conf
    echo 'devd_enable="NO"' >> ${INSTALLUFSDIR}/etc/rc.conf
    echo 'newsyslog_enable="NO"' >> ${INSTALLUFSDIR}/etc/rc.conf
    (cd build/pc-sysinstall && make install DESTDIR=${INSTALLUFSDIR} NO_MAN=t)
    rm ${INSTALLUFSDIR}/etc/rc.conf.local
    rm ${INSTALLUFSDIR}/etc/rc.d/ix-*
    rm ${INSTALLUFSDIR}/etc/rc.d/motd
    rm ${INSTALLUFSDIR}/etc/rc.d/ip6addrctl
    rm ${INSTALLUFSDIR}/etc/rc.initdiskless
    rm -rf ${INSTALLUFSDIR}/bin ${INSTALLUFSDIR}/sbin ${INSTALLUFSDIR}/usr/local
    rm -rf ${INSTALLUFSDIR}/usr/bin ${INSTALLUFSDIR}/usr/sbin
    ln -s ../../rescue ${INSTALLUFSDIR}/usr/bin
    ln -s ../../rescue ${INSTALLUFSDIR}/usr/sbin
    ln -s ../rescue ${INSTALLUFSDIR}/bin
    ln -s ../rescue ${INSTALLUFSDIR}/sbin
    tar -cf - -C${ETC_FILES} . | tar -xvf - -C ${INSTALLUFSDIR}/etc

    # Compress what's left of the image after mangling it
    makefs -b 10%  ${TEMP_IMGFILE} ${INSTALLUFSDIR}
    mkuzip -o ${ISODIR}/data/base.ufs.uzip ${TEMP_IMGFILE}

    # Magic scripts for the LiveCD
    cat > ${STAGEDIR}/baseroot.rc << 'EOF'
#!/bin/sh
#set -x
PATH=/rescue

BASEROOT_MP=/baseroot
RWROOT_MP=/rwroot
CDROM_MP=/cdrom
BASEROOT_IMG=/data/base.ufs.uzip

# Re-mount root R/W, so that we can create necessary sub-directories
mount -u -w /

mkdir -p ${BASEROOT_MP}
mkdir -p ${RWROOT_MP}
mkdir -p ${CDROM_MP}

# mount CD device
mount -t cd9660 /dev/acd0 ${CDROM_MP}

# Mount future live root
mdconfig -a -t vnode -f ${CDROM_MP}${BASEROOT_IMG} -u 9
mount -r /dev/md9.uzip ${BASEROOT_MP}

# Create in-memory filesystem
mdconfig -a -t swap -s 64m -u 10
newfs /dev/md10
mount /dev/md10 ${RWROOT_MP}

# Union-mount it over live root to make it appear as R/W
mount -t unionfs ${RWROOT_MP} ${BASEROOT_MP}

# Mount devfs in live root
DEV_MP=${BASEROOT_MP}/dev
mkdir -p ${DEV_MP}
mount -t devfs devfs ${DEV_MP}

# Make whole CD content available in live root via nullfs
mkdir -p ${BASEROOT_MP}${CDROM_MP}
mount -t nullfs -o ro ${CDROM_MP} ${BASEROOT_MP}${CDROM_MP}

kenv init_shell="/bin/sh"
echo "baseroot setup done"
exit 0
EOF

    makefs -b 10% ${ISODIR}/boot/memroot.ufs ${STAGEDIR}
    gzip -9 ${ISODIR}/boot/memroot.ufs

    # More magic scripts for the LiveCD
    cat > ${ISODIR}/boot/loader.conf << EOF
#
# Boot loader file for FreeNAS.  This relies on a hacked beastie.4th.
#
autoboot_delay="2"
loader_logo="freenas"

mfsroot_load="YES"
mfsroot_type="md_image"
mfsroot_name="/boot/memroot.ufs"

init_path="/rescue/init"
init_shell="/rescue/sh"
init_script="/baseroot.rc"
init_chroot="/baseroot"
opensolaris_load="YES"
zfs_load="YES"
geom_mirror_load="YES"
EOF
    eval ${MKISOFS_CMD}
}

cleanup()
{
    # Clean up directories used to create the liveCD
    rm -rf ${STAGEDIR}
    rm -rf ${ISODIR}
    rm -rf ${INSTALLUFSDIR}
}

main
