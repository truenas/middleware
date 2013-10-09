#!/bin/sh
#-
# Copyright (c) 2013 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

#
# Run the nanobsd updater with the fixed partition image.
#
# Garrett Cooper, March 2012
#
# Run the old updater if we're not absolutely certain we're FreeNAS.

if [ ! \( "$OLD_AVATAR_PROJECT" = "FreeNAS" -a \
    "$NEW_AVATAR_PROJECT" = "FreeNAS" \) ] ; then

    echo "Doing old upgrade" > /data/0005.run_update.sh.log
    date >> /data/0005.run_update.sh.log

    if [ "$VERBOSE" != "" -a "$VERBOSE" != "0" ] ; then
        sh -x $SCRIPTDIR/bin/update $SCRIPTDIR/firmware.img
    else
        sh $SCRIPTDIR/bin/update $SCRIPTDIR/firmware.img
    fi
else
    echo "Doing NEW upgrade" > /data/0005.run_update.sh.log
    date >> /data/0005.run_update.sh.log

. /etc/nanobsd.conf
. /etc/rc.freenas

PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/games:/usr/local/sbin:/usr/local/bin

FREEBSD_RELEASE=`uname -r | cut -f1 -d-`

ROOTDEV=`/sbin/glabel status | /usr/bin/grep ${NANO_DRIVE}s1a | /usr/bin/awk '{print $3;}' | sed -e 's,s1a$,,g'`
if [ -c /dev/${ROOTDEV} ]; then
	ROOTDEV_SIZE=`diskinfo /dev/${ROOTDEV} | awk '{print $3;}'`

	# Check if the root device have enough space to hold new image.
	# TODO: Find a way so we do not hardcode this value.
	if [ ${ROOTDEV_SIZE} -lt 3699999744 ]; then
		warn "Root device too small!"
		exit 1
	fi

	# Check if we need to do a full trampoline upgrade
	ROOTS1_SIZE=`diskinfo /dev/${ROOTDEV}s1 | awk '{print $3;}'`
	ROOTS2_SIZE=`diskinfo /dev/${ROOTDEV}s2 | awk '{print $3;}'`

	if [ ${ROOTS1_SIZE} -ge 1838301696 -a ${ROOTS2_SIZE} -ge 1838301696 ]; then
		# Use "normal" procedure.
		sh $SCRIPTDIR/bin/update $SCRIPTDIR/firmware.img
	else
		# Full trampoline upgrade.

		# We can not do this if our backing storage is a md.
		VOLUME_MOUNTPOINT=`dirname ${SCRIPTDIR}`
		VOLUME_DEVICE=`mount | grep ${VOLUME_MOUNTPOINT} | awk '{print $1;}'`
		if [ "${VOLUME_DEVICE##/dev/md}" != ${VOLUME_DEVICE} ]; then
			warn "Can not do trampoline upgrade without backing storage."
			exit 1
		fi

		if [ "${VOLUME_DEVICE##/dev/}" = ${VOLUME_DEVICE} ]; then
			POOL=${VOLUME_DEVICE%%/*}
			IMPORTCMD="/rescue/zpool import -R /mnt -o readonly=on -f ${POOL}"
			EXPORTCMD="/rescue/zpool export ${POOL}"
		else
			IMPORTCMD="/rescue/mkdir -p ${SCRIPTDIR} ; /rescue/mount -o ro ${VOLUME_DEVICE} ${VOLUME_MOUNTPOINT}"
			EXPORTCMD="/rescue/umount ${VOLUME_MOUNTPOINT}"
		fi
			

		# Create a temporary file
		rm -f ${SCRIPTDIR}/newdisk.img
		truncate -s ${ROOTDEV_SIZE} ${SCRIPTDIR}/newdisk.img
		NEWDISK_MD=`mdconfig -a -t vnode -f ${SCRIPTDIR}/newdisk.img`
		echo "\
g c1023 h16 s63
p 1 165 63 3590433
p 2 165 3590559 3590433
p 3 165 7180992 3024
p 4 165 7184016 41328
a 1" > ${SCRIPTDIR}/newdisk.fdisk
		fdisk -i -f ${SCRIPTDIR}/newdisk.fdisk ${NEWDISK_MD}
		rm -f ${SCRIPTDIR}/newdisk.fdisk

		# Write the binary partition.
		recoverdisk ${SCRIPTDIR}/firmware.img /dev/${NEWDISK_MD}s1
		mkdir -p ${SCRIPTDIR}/mp/newroot
		mount /dev/${NEWDISK_MD}s1a ${SCRIPTDIR}/mp/newroot

		# Write MBR
		boot0cfg -B -b ${SCRIPTDIR}/mp/newroot/boot/boot0 -o packet -s 1 -m 3 -t 18 ${NEWDISK_MD}

		NANO_LABEL=`echo ${NANO_DRIVE} | cut -f2 -d/`

		# Populate /data and /cfg partitions
		newfs -b 4096 -f 512 -i 8192 -O1 -U -L ${NANO_LABEL}s3 /dev/${NEWDISK_MD}s3
		newfs -b 4096 -f 512 -i 8192 -O1 -U -L ${NANO_LABEL}s4 /dev/${NEWDISK_MD}s4

		# Copy over our /data to new /data, and copy files in /root to new image.
		rm -fr ${SCRIPTDIR}/mp/newroot/data
		mkdir -p ${SCRIPTDIR}/mp/newroot/data
		mount /dev/${NEWDISK_MD}s4 ${SCRIPTDIR}/mp/newroot/data
		rsync -au /root/ ${SCRIPTDIR}/mp/newroot/root/
		rsync -a /data/ ${SCRIPTDIR}/mp/newroot/data/
		# Touch update sentinals, this is similar to a CD upgrade case.
		touch ${SCRIPTDIR}/mp/newroot${NEED_UPDATE_SENTINEL}
		touch ${SCRIPTDIR}/mp/newroot${CD_UPGRADE_SENTINEL}
		umount ${SCRIPTDIR}/mp/newroot/data/

		# Create the trampoline filesystem.
		if mount | grep ${NANO_DRIVE}s1 > /dev/null ; then
			CURRENT_SLICE=1
			TRAMPOLINE_SLICE=2
		else
			CURRENT_SLICE=2
			TRAMPOLINE_SLICE=1
		fi
		TRAMPOLINE_SIZE=`diskinfo /dev/${ROOTDEV}s${TRAMPOLINE_SLICE} | awk '{print $3;}'`
		rm -f ${SCRIPTDIR}/trampoline.img
		truncate -s ${TRAMPOLINE_SIZE} ${SCRIPTDIR}/trampoline.img
		TRAMPOLINE_MD=`mdconfig -a -t vnode -f ${SCRIPTDIR}/trampoline.img`
		bsdlabel -w -B /dev/${TRAMPOLINE_MD}
		newfs -b 4096 -f 512 -i 8192 -O1 -U /dev/${TRAMPOLINE_MD}a
		mkdir -p ${SCRIPTDIR}/mp/trampoline
		mount /dev/${TRAMPOLINE_MD}a ${SCRIPTDIR}/mp/trampoline
		rsync -a ${SCRIPTDIR}/mp/newroot/boot ${SCRIPTDIR}/mp/trampoline/

		# Generate trampoline memdisk files
		rm -fr ${SCRIPTDIR}/mp/trampoline-mfs
		mkdir -p ${SCRIPTDIR}/mp/trampoline-mfs
		tar cf - -C ${SCRIPTDIR}/mp/newroot/ rescue | tar xf - -C ${SCRIPTDIR}/mp/trampoline-mfs
		mkdir -p ${SCRIPTDIR}/mp/trampoline-mfs/dev
		mkdir -p ${SCRIPTDIR}/mp/trampoline-mfs/mnt
		mkdir -p ${SCRIPTDIR}/mp/trampoline-mfs/nextroot

		# The trampoline script
		cat > ${SCRIPTDIR}/mp/trampoline-mfs/upgrade-trampoline.rc <<-EOF
#!/bin/sh

mdmfs -s 8m md /mnt

${IMPORTCMD}

if [ -e ${SCRIPTDIR}/newdisk.img ]; then
	echo "Upgrade is being applied, please be patient..."
	dd if=${SCRIPTDIR}/newdisk.img of=/dev/${ROOTDEV} bs=1m
	umount ${SCRIPTDIR}/..
	${EXPORTCMD}
	mount -o ro /dev/${NANO_DRIVE}s1a /nextroot
	mount -t devfs devfs /nextroot/dev
else
	echo "Upgrade FAILED!  Reverting to previous state..."
	/rescue/gpart set -a active -i ${CURRENT_SLICE} ${ROOTDEV}
	/rescue/sleep 15
	echo "Rebooting..."
	/rescue/reboot
	exit 0
fi

/rescue/gpart set -a active -i 1 ${ROOTDEV}

kenv init_shell="/bin/sh"
echo "Done, let's try migrate the data..."
exit 0
EOF


		# Create the trampoline MFS image
		makefs ${SCRIPTDIR}/mp/trampoline/boot/trampoline.ufs ${SCRIPTDIR}/mp/trampoline-mfs/
		rm -fr ${SCRIPTDIR}/mp/trampoline-mfs/

		# Create loader.conf
		cat > ${SCRIPTDIR}/mp/trampoline/boot/loader.conf <<-EOF
autoboot_delay="0"
beastie_disable="YES"

mfsroot_load="YES"
mfsroot_type="md_image"
mfsroot_name="/boot/trampoline.ufs"

init_path="/rescue/init"
init_shell="/rescue/sh"
init_script="/upgrade-trampoline.rc"
init_chroot="/nextroot"

zfs_load="YES"
EOF

		umount ${SCRIPTDIR}/mp/trampoline
		mdconfig -d -u ${TRAMPOLINE_MD##md}
		umount ${SCRIPTDIR}/mp/newroot

		recoverdisk ${SCRIPTDIR}/trampoline.img /dev/${ROOTDEV}s${TRAMPOLINE_SLICE}
		rm -f ${SCRIPTDIR}/trampoline.img
		gpart set -a active -i ${TRAMPOLINE_SLICE} ${ROOTDEV}
	fi
else
	warn "Can not determine root device"
	exit 1
fi

fi
