#!/bin/sh

# This script creates a bootable LiveCD iso from a nanobsd image

trap make_pristine 1 2 3 6

main()
{
    # This script must be run as root
    if ! [ $(whoami) = "root" ]; then
        echo "This script must be run by root"
        exit
    fi

    # Paths that may need altering on the build system
    IMGFILE="/home/jpaetzel/FreeNAS-8r5375-amd64.full.gz" # The FreeNAS image
    BOOTFILE="/home/jpaetzel/ix2/build/files/cd.img" # The image used to make the CD
    TEMP_IMGFILE="/usr/newfile" # Scratch file for image
    INSTALL_SH="/home/jpaetzel/ix2/build/files/install.sh"
    RC_FILE="/home/jpaetzel/ix2/build/files/rc"
    RESCUE_TAR="/home/jpaetzel/ix2/build/files/rescue.tar"

    # Various mount points needed to build the CD, adjust to taste
    STAGEDIR="/tmp/stage" # Scratch location for making filesystem image
    ISODIR="/tmp/iso" # Directory ISO is rolled from
    SRC_MNTPOINT="/mnt" # Scratch mountpoint where the image will be dissected
    DEST_MNTPOINT="/mnt2" # Destination mountpoint for image

    OUTPUT="fn2.iso" # Output file of mkisofs

    # A command forged by the gods themselves, change at your own risk
    MKISOFS_CMD="/usr/local/bin/mkisofs -R -l -ldots -allow-lowercase \
                 -allow-multidot -hide boot.catalog -o ${OUTPUT} -no-emul-boot \
                 -b boot/cdboot ${ISODIR}"

    # END OF CONFIGURATION SECTION
    BOOTFILE_MD=`md5 ${BOOTFILE} | awk '{print $4}'`

    cleanup
    prep_imgfile_dest

    mkdir -p ${STAGEDIR}/dev
    mkdir -p ${ISODIR}/data

    # Do this early because we are going to be mangling the image.
    # Please beware that interrupting this command with ctrl-c will
    # cause cleanup() to run, which attempts to restore the original
    # image.  If this copy isn't completed bad things can happen.  Moral
    # of the story: keep a pristine image around.

    cp ${BOOTFILE} ${BOOTFILE}.orig

    # move /boot from the image to the iso
    md=`mdconfig -a -t vnode -f ${BOOTFILE}`
    mount /dev/${md}s1a ${SRC_MNTPOINT}

    rm -rf ${SRC_MNTPOINT}/rescue
    mkdir ${SRC_MNTPOINT}/rescue
    mkdir ${STAGEDIR}/rescue
    tar -xvf ${RESCUE_TAR} -C ${SRC_MNTPOINT}/rescue
    tar -xvf ${RESCUE_TAR} -C ${STAGEDIR}/rescue
    mv ${SRC_MNTPOINT}/boot ${ISODIR}/
    cp ${IMGFILE} ${ISODIR}/FreeNAS-amd64-embedded.gz

    echo "#/dev/md0 / ufs ro 0 0" > ${SRC_MNTPOINT}/etc/fstab
    echo 'root_rw_mount="NO"' >> ${SRC_MNTPOINT}/etc/rc.conf
    sed -i "" -e 's/^\(sshd.*\)".*"/\1"NO"/' ${SRC_MNTPOINT}/etc/rc.conf
    sed -i "" -e 's/^\(light.*\)".*"/\1"NO"/' ${SRC_MNTPOINT}/etc/rc.conf
    echo 'cron_enable="NO"' >> ${SRC_MNTPOINT}/etc/rc.conf
    echo 'syslogd_enable="NO"' >> ${SRC_MNTPOINT}/etc/rc.conf
    echo 'inetd_enable="NO"' >> ${SRC_MNTPOINT}/etc/rc.conf
    echo 'devd_enable="NO"' >> ${SRC_MNTPOINT}/etc/rc.conf
    echo 'newsyslog_enable="NO"' >> ${SRC_MNTPOINT}/etc/rc.conf
    # Had to hack pc-sysinstall to install to /rescue, troubleshoot why
    (cd /home/jpaetzel/pc-sysinstall && make install DESTDIR=${SRC_MNTPOINT})
    rm ${SRC_MNTPOINT}/etc/rc.conf.local
    rm ${SRC_MNTPOINT}/etc/rc.d/ix-*
    rm ${SRC_MNTPOINT}/etc/rc.d/motd
    rm ${SRC_MNTPOINT}/etc/rc.d/ip6addrctl
    rm ${SRC_MNTPOINT}/etc/rc.initdiskless
    rm -rf ${SRC_MNTPOINT}/bin ${SRC_MNTPOINT}/sbin ${SRC_MNTPOINT}/usr/local
    rm -rf ${SRC_MNTPOINT}/usr/bin ${SRC_MNTPOINT}/usr/sbin
    ln -s ../../rescue ${SRC_MNTPOINT}/usr/bin
    ln -s ../../rescue ${SRC_MNTPOINT}/usr/sbin
    ln -s ../rescue ${SRC_MNTPOINT}/bin
    ln -s ../rescue ${SRC_MNTPOINT}/sbin
    cp ${RC_FILE} ${SRC_MNTPOINT}/etc/
    cp ${INSTALL_SH} ${SRC_MNTPOINT}/etc/
    chmod 755 ${SRC_MNTPOINT}/etc/install.sh
    chown root:wheel ${SRC_MNTPOINT}/etc/install.sh

    dump -0Laf - /dev/${md}s1a | ( cd ${DEST_MNTPOINT} && restore -rf -)
    unmount ${SRC_MNTPOINT} ${md}
    rm ${DEST_MNTPOINT}/restore*
    unmount ${DEST_MNTPOINT} ${md_tmp}
    # Compress what's left of the image after mangling it
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
    gzip ${ISODIR}/boot/memroot.ufs

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
    if [ -d ${STAGEDIR} ]; then
        rm -rf ${STAGEDIR}
    fi

    if [ -d ${ISODIR} ]; then
        rm -rf ${ISODIR}
    fi
}

make_pristine()
{
    # Put everything back the way it was before this script was run
    cleanup
    unmount ${SRC_MNTPOINT} ${md}
    unmount ${DEST_MNTPOINT} ${md_tmp}

    CURR_BOOTFILE_MD=`md5 ${BOOTFILE} | awk '{print $4}'`
    if [ "${CURR_BOOTFILE_MD}" = "${BOOTFILE_MD}" ]; then
        if [ -f ${BOOTFILE}.orig ]; then
            rm ${BOOTFILE}.orig
        fi
        exit
    fi


    if [ -f ${BOOTFILE}.orig ]; then
        MD=`md5 ${BOOTFILE}.orig | awk '{print $4}'`
        if [ ${MD} = ${BOOTFILE_MD} ]; then
            mv ${BOOTFILE}.orig ${BOOTFILE}
        fi
    fi
}

unmount()
{
    local MNTPOINT=$1
    local MD=$2

    md_val=`echo ${MD} | sed s/^md//`
    df ${MNTPOINT} | grep ${MNTPOINT} > /dev/null
    if [ "$?" = "0" ]; then
        while [ 1 ]
        do
            umount ${MNTPOINT}
            if  [ "$?" = "0" ]; then
                break
            fi
            echo "umount of ${MNTPOINT} failed! Trying again"
            sleep 3
        done
    fi
    mdconfig -l -u ${md_val}
    if [ "$?" = "0" ]; then
        mdconfig -d -u ${md_val}
    fi

}

prep_imgfile_dest()
{
    if [ -f ${TEMP_IMGFILE} ]; then
        rm ${TEMP_IMGFILE}
    fi
    dd if=/dev/zero of=${TEMP_IMGFILE} bs=1m count=1 seek=45
    md_tmp=`mdconfig -a -t vnode -f ${TEMP_IMGFILE}`
    newfs /dev/${md_tmp}
    mount /dev/${md_tmp} ${DEST_MNTPOINT}
}

main
make_pristine
