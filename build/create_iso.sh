
#!/bin/sh

set -e

mydir=`dirname $0`
. "$mydir/make_install_fs.sh"

common_installfs "${NANO_OBJ}/_.isodir"

# This script creates a bootable LiveCD ISO from a nanobsd image for FreeNAS
if ! command -v mkisofs >/dev/null 2>&1; then
    error "mkisofs not available.  Please install the sysutils/cdrtools port."
fi

build_installfs  "${NANO_OBJ}/_.isodir"

	OUTPUT="${NANO_OBJ}/$NANO_NAME.iso" # Output file of mkisofs
	CDROM_LABEL=${NANO_LABEL}_INSTALL
	MKISOFS_CMD="/usr/local/bin/mkisofs -R -l -ldots -allow-lowercase \
			 -allow-multidot -hide boot.catalog -V ${CDROM_LABEL} -o ${OUTPUT} -no-emul-boot \
			 -b boot/cdboot ${STAGE_DIR}"

	cp -p ${AVATAR_ROOT}/build/files/loader.conf.cdrom ${STAGE_DIR}/boot/loader.conf
	sed -i "" 's/%CDROM_LABEL%/'${CDROM_LABEL}'/'  ${STAGE_DIR}/boot/loader.conf
	sed -i "" 's/%NANO_LABEL_LOWER%/'${NANO_LABEL_LOWER}'/'  ${STAGE_DIR}/boot/loader.conf
	cp -p ${AVATAR_ROOT}/build/files/mount.conf.cdrom ${STAGE_DIR}/.mount.conf

	eval ${MKISOFS_CMD}
        ( cd $NANO_OBJ
          sha256_signature=`sha256 ${NANO_NAME}.iso`
          echo "${sha256_signature}" > ${NANO_NAME}.iso.sha256.txt
        )

	echo "Created ${OUTPUT}"
