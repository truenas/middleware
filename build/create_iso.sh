#!/bin/sh

# This script creates a bootable LiveCD iso from a nanobsd image

trap make_pristine 1 2 3 6

main()
{
    IMGFILE="/home/jpaetzel/FreeNAS-8r561-amd64.full" # Our starting point
    IMGFILE_MD=`md5 ${IMGFILE} | awk '{print $4}'`
    STAGEDIR="/tmp/stage" # Scratch location for making filesystem image
    ISODIR="/tmp/iso" # Directory ISO is rolled from
    OUTPUT="fn2.iso" # Output file of mkisofs
    MNTPOINT="/mnt" # Scratch mountpoint where the image will be dissected

    MKISOFS_CMD="/usr/local/bin/mkisofs -R -l -ldots -allow-lowercase \
                 -allow-multidot -hide boot.catalog -o ${OUTPUT} -no-emul-boot \
                 -b boot/cdboot ${ISODIR}"

    cleanup

    mkdir -p ${STAGEDIR}/dev
    mkdir -p ${ISODIR}/data

    # Do this early because we are going to be molesting the image.
    # Please beware that interrupting this command with ctrl-c will
    # cause cleanup() to run, which attempts to restore the original
    # image.  If this copy isn't completed bad things can happen.  Moral
    # of the story: keep a pristine image around.

    cp ${IMGFILE} ${IMGFILE}.orig

    # move /boot from the image to the iso
    md=`mdconfig -a -t vnode -f ${IMGFILE}`

    # s1a is hard coded here and dependant on the image.
    mount /dev/${md}s1a /mnt

    mkdir ${STAGEDIR}/rescue
    (cd /mnt/rescue && tar cf - . ) | (cd ${STAGEDIR}/rescue && tar xf - )
    cp -R /mnt/boot ${ISODIR}/

    # Compress what's left of the image after mangling it
    mkuzip -o ${ISODIR}/data/base.ufs.uzip ${IMGFILE}

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
mount -r /dev/md9.uzips1a ${BASEROOT_MP}

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
    umount /mnt
    mdconfig -d -u `echo ${md} | sed s/^md//`

    CURR_IMGFILE_MD=`md5 ${IMGFILE} | awk '{print $4}'`
    if [ "${CURR_IMGFILE_MD}" = "${IMGFILE_MD}" ]; then
        if [ -f ${IMGFILE}.orig ]; then
            rm ${IMGFILE}.orig
        fi
        exit
    fi


    if [ -f ${IMGFILE}.orig ]; then
        MD=`md5 ${IMGFILE}.orig | awk '{print $4}'`
        if [ ${MD} = ${IMGFILE_MD} ]; then
            mv ${IMGFILE}.orig ${IMGFILE}
        fi
    fi
}

main
make_pristine
