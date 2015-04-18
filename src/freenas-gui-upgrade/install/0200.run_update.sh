#!/bin/sh
#-
# Copyright (c) 2014 iXsystems, Inc.
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

PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/games:/usr/local/sbin:/usr/local/bin

. /etc/avatar.conf
. /etc/nanobsd.conf
. /etc/rc.freenas

upgrade_cleanup()
{
	find ${SCRIPTDIR} -type f -exec truncate -s 0 {} +
}

upgrade_fail()
{
	warn $1
	upgrade_cleanup
	exit 1
}

standard_upgrade()
{
	# To upgrade a system that is already based on the new package/installation
	# system, we need to use freenas-install.  First, though, we need to
	# make a BE clone, and snapshot the grub filesystem.
	# Unlike the trampoline install, we've got the basics we need in
	# place, so we only have to be concerned with gui-packages.tar.
    set -x
	OS=${AVATAR_PROJECT}
	UPGRADE_DIR=${SCRIPTDIR}/update
	mkdir -p ${UPGRADE_DIR} || upgrade_fail "Unable to create package directory"
	tar xf ${SCRIPTDIR}/gui-packages.tar -C ${UPGRADE_DIR} || upgrade_fail "Unable to extract package files"
	NEW_VERSION=${OS}-$(/usr/local/bin/manifest_util -M ${UPGRADE_DIR}/${OS}-MANIFEST sequence)
	if [ "${NEW_VERSION}" = "${OS}-" ]; then
	    upgrade_fail "Unable to determine sequence for new version"
	fi
	beadm create "${NEW_VERSION}" || upgrade_fail "Unable to create new boot environment"
	if zfs snapshot freenas-boot/boot/grub@Pre-Upgrade-${NEW_VERSION}; then
	    grub_clone=true
	else
	    grub_clone=false
	fi
	dest=$(mktemp -d upgrade-XXXXXX)
	if [ -z "${dest}" ]; then
	    upgrade_fail "Could not create temporary directory"
	fi
	if ! beadm mount "${NEW_VERSION}" ${dest}; then
	    beadm destroy -F "${NEW_VERSION}" || true
	    ${grub_clone} && zfs destroy freenas-boot/boot/grub@Pre-Upgrade-${NEW_VERSION}
	    upgrade_fail "Could not mount new boot environment"
	fi
	mount -t nullfs /boot/grub ${dest}/boot/grub
	/usr/local/bin/freenas-install -M ${UPGRADE_DIR}/${OS}-MANIFEST \
	    -P ${UPGRADE_DIR}/Packages ${dest}
	rv=$?
	umount ${dest}/boot/grub
	beadm unmount ${NEW_VERSION}
	if [ $rv -ne 0 ]; then
	    beadm destroy -F ${NEW_VERSION}
	    upgrade_fail "Could not install new version"
	else
	    beadm activate ${NEW_VERSION}
	fi
	zpool scrub freenas-boot || true
	set +x
}

trampoline_upgrade()
{
	# Trampoline upgrade.  Determine eligibility.
	ROOTDEV=`/sbin/glabel status | /usr/bin/grep ${NANO_DRIVE}s1a | /usr/bin/awk '{print $3;}' | sed -e 's,s1a$,,g'`
	if [ -c /dev/${ROOTDEV} ]; then
		ROOTDEV_SIZE=`diskinfo /dev/${ROOTDEV} | awk '{print $3;}'`

		# Check if the root device have enough space to hold new image.
		# TODO: Find a way so we do not hardcode this value.
		if [ ${ROOTDEV_SIZE} -lt 3699999744 ]; then
			upgrade_fail "Root device too small!"
		fi
	fi

	# ${SCRIPTDIR} has the contents of the GUI upgrade file, extracted.
	# Files we need to concern ourselves with:
	# gui-boot.tar -- /boot
	# gui-install-environment.tar -- the installation environment.  Also /rescue
	# gui-packages.tar -- the packages (should be extracted into .mount)
	#
	# Everything goes under ${TRAMPOLINE_MP}
	
	# We need to have /boot in ${TRAMPOLINE_MFS_ROOT.
	# We need to put /rescue in ${TRAMPOLINE_MFS_ROOT}
	# We need to copy gui-install-environment.tar and gui-packages.tar to
	# ${TRAMPOLINE_IMG}, which will be recoverdisk'd to the filesystem.
	MP_ROOTS=${SCRIPTDIR}/tmp/mp
	mkdir -p ${MP_ROOTS}

	# Extract the installation image for future use
	INSTALLATION_ROOT=${SCRIPTDIR}/tmp/newroot
	rm -rf ${INSTALLATION_ROOT} || chflags -R 0 ${INSTALLATION_ROOT} && rm -fr ${INSTALLATION_ROOT}
	mkdir -p ${INSTALLATION_ROOT}

#	INSTALLATION_MD=`mdconfig -a -o ro -t vnode -f ${INSTALLATION_IMG}`
#	INSTALLATION_MD_ROOT=${MP_ROOTS}/install

#	mkdir -p ${INSTALLATION_MD_ROOT}
#	mount -o ro ${INSTALLATION_MD} ${INSTALLATION_MD_ROOT}
	trap "umount ${INSTALLATION_MD_ROOT} && mdconfig -d -u ${INSTALLATION_MD##md}" 1 2 15 EXIT
#	tar cf - -C ${INSTALLATION_MD_ROOT} | tar xf - -C ${INSTALLATION_ROOT}
#	umount ${INSTALLATION_MD_ROOT}
#	mdconfig -d -u ${INSTALLATION_MD##md}
	trap 1 2 15 EXIT

	# Data to be migrated into the new system
#	tar cf - /data /root/.ssh | tar xf - -C ${INSTALLATION_ROOT}
	# Touch sentinals to simulate CD-ROM upgrade (except we don't have a returning ticket)
#	touch ${INSTALLATION_ROOT}${NEED_UPDATE_SENTINEL}
#	touch ${INSTALLATION_ROOT}${CD_UPGRADE_SENTINEL}

	#
	# Create the trampoline MFS image.  This MFS image does the following:
	#
	# 1. Mount the real / (file system where it booted from) read-only at /mnt
	# 2. Create a memory file system at /installer and copy the full FreeNAS
	#    image into memory. (we already copied /data there)
	# 3. Unmount the real / mounted at /mnt.  Now we can write the ${ROOTDEV}
	# 4. Chroot into the image and have the real installer core to perform
	#    the actual installation against ${ROOTDEV}
	#
	TRAMPOLINE_MFS_ROOT=${SCRIPTDIR}/tmp/trampoline_mfsroot
	TRAMPOLINE_MFS_IMG=${SCRIPTDIR}/tmp/trampoline.ufs
	TRAMPOLINE_MFS_RC=trampoline.rc
	rm -fr ${TRAMPOLINE_MFS_ROOT}
	mkdir -p ${TRAMPOLINE_MFS_ROOT}

	# Mountpoints
	mkdir -p ${TRAMPOLINE_MFS_ROOT}/dev
	mkdir -p ${TRAMPOLINE_MFS_ROOT}/mnt
	mkdir -p ${TRAMPOLINE_MFS_ROOT}/installer
	mkdir -p ${TRAMPOLINE_MFS_ROOT}/installer/dev
	mkdir -p ${TRAMPOLINE_MFS_ROOT}/installer/.mount/${AVATAR_PROJECT}
	
	# Copy /rescue from the installation image.
	tar xf ${SCRIPTDIR}/gui-install-environment.tar -C ${TRAMPOLINE_MFS_ROOT} ./rescue

	# Determine the running slice and the target slice
	if mount | grep ${NANO_DRIVE}s1 > /dev/null ; then
		CURRENT_SLICE=1
		TRAMPOLINE_SLICE=2
	else
		CURRENT_SLICE=2
		TRAMPOLINE_SLICE=1
	fi

	# The trampoline script
	##########################################
	cat > ${TRAMPOLINE_MFS_ROOT}/${TRAMPOLINE_MFS_RC} <<-EOF
#!/bin/sh

echo -n "Extracting upgrade image, please wait..."

/rescue/mount -o ro /dev/${ROOTDEV}s${TRAMPOLINE_SLICE}a /mnt
/rescue/mount -t tmpfs tmpfs /installer
/rescue/mkdir -p /installer/.mount/${AVATAR_PROJECT}

/rescue/tar xf /mnt/gui-install-environment.tar  -C /installer || (echo "FAILED BASE EXTRACTION" && /bin/sh && /rescue/sleep 15 && /rescue/reboot)
/rescue/tar xf /mnt/gui-packages.tar -C /installer/.mount || (echo "FAILED PACKAGE EXTRACTION" && /bin/sh && /rescue/sleep 15 && /rescue/reboot)
/rescue/mv /installer/.mount/Packages /installer/.mount/${AVATAR_PROJECT}/Packages
/rescue/umount /mnt

echo " Done!"
echo -n "Applying upgrade..."

# Set up chroot jail for the first time installer
/rescue/mount -t devfs devfs /installer/dev
#echo "Starting a shell now; exit when done"
#/rescue/sh

/rescue/chroot /installer /bin/sh /etc/install.sh "${ROOTDEV}" || (echo "FAILED" && /bin/sh && /bin/sh && /rescue/reboot)
echo " Done!"
echo "Rebooting..."
/rescue/reboot
EOF
	##########################################
	# The trampoline script, end.

	# Create the trampoline MFS image
	makefs ${TRAMPOLINE_MFS_IMG} ${TRAMPOLINE_MFS_ROOT}
#	rm -fr ${TRAMPOLINE_MFS_ROOT} &
	gzip -9 ${TRAMPOLINE_MFS_IMG}

	# Trampoline partition.  This contains:
	# 1. The kernel to boot the system;
	# 2. The trampoline MFS image, loaded via loader on boot;
	# 3. The installation image, re-packed because we modified its contents;
	TRAMPOLINE_IMG=${SCRIPTDIR}/tmp/trampoline.img
	TRAMPOLINE_SIZE=`diskinfo /dev/${ROOTDEV}s${TRAMPOLINE_SLICE} | awk '{print $3;}'`
	TRAMPOLINE_MP=${SCRIPTDIR}/tmp/mp

	rm -f ${TRAMPOLINE_IMG}
	truncate -s ${TRAMPOLINE_SIZE} ${TRAMPOLINE_IMG}
	TRAMPOLINE_MD=`mdconfig -a -t vnode -f ${TRAMPOLINE_IMG}`
	bsdlabel -w -B /dev/${TRAMPOLINE_MD}
	newfs -b 4096 -f 512 -i 8192 -O1 -U /dev/${TRAMPOLINE_MD}a

	mkdir -p ${TRAMPOLINE_MP}
	mount /dev/${TRAMPOLINE_MD}a ${TRAMPOLINE_MP}

	# Get /boot into ${TRAMPOLINE_MP}
	tar xf ${SCRIPTDIR}/gui-boot.tar -C ${TRAMPOLINE_MP} ./boot
	mv ${TRAMPOLINE_MFS_IMG}.gz ${TRAMPOLINE_MP}/boot/
	cp ${SCRIPTDIR}/gui-install-environment.tar ${TRAMPOLINE_MP}
	cp ${SCRIPTDIR}/gui-packages.tar ${TRAMPOLINE_MP}

	# Create loader.conf
	TARGET_MFS=/boot/$(basename ${TRAMPOLINE_MFS_IMG})
	cat > ${TRAMPOLINE_MP}/boot/loader.conf <<-EOF
autoboot_delay="0"
beastie_disable="YES"

mfsroot_load="YES"
mfsroot_type="md_image"
mfsroot_name="${TARGET_MFS}"

init_path="/rescue/init"
init_shell="/rescue/sh"
init_script="/${TRAMPOLINE_MFS_RC}"
tmpfs_load="YES"
EOF

	umount ${TRAMPOLINE_MP}
	mdconfig -d -u ${TRAMPOLINE_MD##md}
	recoverdisk ${TRAMPOLINE_IMG} /dev/${ROOTDEV}s${TRAMPOLINE_SLICE}
	rm -f ${TRAMPOLINE_IMG}
	gpart set -a active -i ${TRAMPOLINE_SLICE} ${ROOTDEV}
}

if [ ! -d /.zfs ]; then
	trampoline_upgrade
else
	standard_upgrade
fi

upgrade_cleanup
exit 0
