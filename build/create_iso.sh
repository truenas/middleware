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

    IMGFILE="/home/jpaetzel/FreeNAS-8r561-amd64.full.gz" # The FreeNAS image
    BOOTFILE="/home/jpaetzel/josh.img" # The image used to make the CD
    BOOTFILE_MD=`md5 ${BOOTFILE} | awk '{print $4}'`
    STAGEDIR="/tmp/stage" # Scratch location for making filesystem image
    ISODIR="/tmp/iso" # Directory ISO is rolled from
    OUTPUT="fn2.iso" # Output file of mkisofs
    MNTPOINT="/mnt" # Scratch mountpoint where the image will be dissected
    INSTALL_SH="/home/jpaetzel/ix2/build/install.sh"
    RC_FILE="/home/jpaetzel/rc"

    MKISOFS_CMD="/usr/local/bin/mkisofs -R -l -ldots -allow-lowercase \
                 -allow-multidot -hide boot.catalog -o ${OUTPUT} -no-emul-boot \
                 -b boot/cdboot ${ISODIR}"

    cleanup

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
    mount /dev/${md} ${MNTPOINT}

    # This is very byzantine, as we are moving the rescue we want into
    # the boot image, only to copy it to the CD.
    # TODO The image doesn't need /boot
    mkdir ${STAGEDIR}/rescue
    (cd /mnt/rescue && tar cf - . ) | (cd ${STAGEDIR}/rescue && tar xf - )
    cp -R ${MNTPOINT}/boot ${ISODIR}/
    cp ${IMGFILE} ${ISODIR}/FreeNAS-amd64-embedded.gz

    # In order for any of this to make any difference to the image file
    # it needs to be dump/restored
    #echo "#/dev/md0 / ufs ro 0 0" > ${MNTPOINT}/etc/fstab
    #echo 'root_rw_mount="NO"' >> ${MNTPOINT}/etc/rc.conf
    #sed -i "" -e 's/^\(sshd.*\)".*"/\1"NO"/' ${MNTPOINT}/etc/rc.conf
    #sed -i "" -e 's/^\(light.*\)".*"/\1"NO"/' ${MNTPOINT}/etc/rc.conf
    #echo 'cron_enable="NO"' >> ${MNTPOINT}/etc/rc.conf
    #echo 'syslogd_enable="NO"' >> ${MNTPOINT}/etc/rc.conf
    #echo 'inetd_enable="NO"' >> ${MNTPOINT}/etc/rc.conf
    #echo 'devd_enable="NO"' >> ${MNTPOINT}/etc/rc.conf
    #echo 'newsyslog_enable="NO"' >> ${MNTPOINT}/etc/rc.conf
    # Had to hack pc-sysinstall to install to /rescue, troubleshoot why
    #(cd /home/jpaetzel/pc-sysinstall && make install DESTDIR=${MNTPOINT})
    #rm ${MNTPOINT}/etc/rc.conf.local
    #rm ${MNTPOINT}/etc/rc.d/ix-*
    #rm ${MNTPOINT}/etc/rc.d/motd
    #rm ${MNTPOINT}/etc/rc.d/ip6addrctl
    #rm ${MNTPOINT}/etc/rc.initdiskless
    #rm -rf ${MNTPOINT}/bin ${MNTPOINT}/sbin ${MNTPOINT}/usr/local/lib*
    #rm -rf ${MNTPOINT}/usr/bin ${MNTPOINT}/usr/sbin ${MNTPOINT}/usr/local/lib*
    #rm -rf ${MNTPOINT}/usr/local/bin ${MNTPOINT}/usr/local/etc
    #ln -s /rescue ${MNTPOINT}/usr/bin
    #ln -s /rescue ${MNTPOINT}/usr/sbin
    #ln -s /rescue ${MNTPOINT}/bin
    #ln -s /rescue ${MNTPOINT}/sbin
    #cp ${RC_FILE} ${MNTPOINT}/etc/
    #cp ${INSTALL_SH} ${MNTPOINT}/etc/
    #chmod 755 /mnt/etc/install.sh
    #chown root:wheel ${MNTPOINT}/etc/install.sh
    unmount

    # Compress what's left of the image after mangling it
    mkuzip -o ${ISODIR}/data/base.ufs.uzip ${BOOTFILE}

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
    unmount

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
    md_val=`echo ${md} | sed s/^md//`
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

main
make_pristine
