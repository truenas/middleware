#!/bin/sh
#-
# Copyright (c) 2010-2011 iXsystems, Inc., All rights reserved.
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
# ARE DISCLAIMED.  IN NO EVENT SHALL iXsystems, Inc. OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
# This file is heavily derived from both Sam Leffler's Avilia config,
# as well as the BSDRP project's config file.  Neither of these have
# an explicit copyright/license statement, but are implicitly BSDL.
#

#
# FreeNAS specific bits of the common stuff.
#

hack_nsswitch_conf ( )
{
	# Remove all references to NIS in the nsswitch.conf file
	# Not sure this is still needed, but FreeNAS has it...
	sed -i.bak -es/nis/files/g ${NANO_WORLDDIR}/etc/nsswitch.conf
	rm -f ${NANO_WORLDDIR}/etc/nsswitch.conf.bak
}

write_version_file ( )
{
	VERSION_FILE=${NANO_WORLDDIR}/etc/version
	if [ "${SVNREVISION}" = "${REVISION}" ]; then
		echo "${NANO_NAME}" > "${VERSION_FILE}"
	else
		echo "${NANO_NAME} (${SVNREVISION})" > "${VERSION_FILE}"
	fi
}

# Move the $world/data to the /data partion
move_data()
{
	db=${NANO_WORLDDIR}/data
	rm -rf ${NANO_DATADIR}
	mkdir -p ${NANO_DATADIR}
	( cd ${db} ; find . | cpio -R root:wheel -dumpv ${NANO_DATADIR} )
	rm -rf ${db}
}

select_httpd ( )
{
	echo 'nginx_enable="YES"' >> ${NANO_WORLDDIR}/etc/rc.conf
}

remove_patch_divots ( )
{
	find ${NANO_WORLDDIR} -name \*.orig -or -name \*.rej -delete
}

configure_mnt_md ( )
{
	mkdir -m 755 -p ${NANO_WORLDDIR}/conf/base/mnt
	echo 8192 > ${NANO_WORLDDIR}/conf/base/mnt/md_size
}

shrink_md_fbsize()
{
	# We have a lot of little files on our memory disks. Let's decrease
	# the block and frag size to fit more little files on them (this
	# halves our space requirement by ~50% on /etc and /var on 8.x --
	# and gives us more back on 9.x as the default block and frag size
	# are 4 times larger).
	sed -i '' -e 's,-S -i 4096,-S -i 4096 -b 4096 -f 512,' \
		${NANO_WORLDDIR}/etc/rc.initdiskless
}

unmute_console_logging()
{
	# /var is small. Don't fill it up with messages from console.log
	# because it's a chatty log.
	sed -i '' -e 's/#console.info/console.info/' \
			"${NANO_WORLDDIR}/etc/syslog.conf"
}

remove_gcc47()
{
	local files_to_save="
/usr/local/lib/gcc47/libstdc++.so.6
/usr/local/lib/gcc47/libstdc++.so
/usr/local/lib/gcc47/libstdc++.a
/usr/local/lib/gcc47/libmudflap.so.0
/usr/local/lib/gcc47/libmudflap.so
/usr/local/lib/gcc47/libmudflapth.so.0
/usr/local/lib/gcc47/libmudflapth.so
/usr/local/lib/gcc47/libssp.so.0
/usr/local/lib/gcc47/libssp.so
/usr/local/lib/gcc47/libgcc_s.so.1
/usr/local/lib/gcc47/libgcc_s.so
/usr/local/lib/gcc47/libquadmath.so.0
/usr/local/lib/gcc47/libquadmath.so
/usr/local/lib/gcc47/libquadmath.a
/usr/local/lib/gcc47/libgomp.spec
/usr/local/lib/gcc47/libgomp.so.1
/usr/local/lib/gcc47/libgomp.so
/usr/local/lib/gcc47/libitm.spec
/usr/local/lib/gcc47/libitm.so.1
/usr/local/lib/gcc47/libitm.so
/usr/local/libdata/ldconfig/gcc47
	"

	echo "Backing up gcc47 libraries"
	for f in $files_to_save
	do
		CR "mv $f $f.bak"
	done
	echo "Removing gcc47" 
	if [ -n "$WITH_PKGNG" ]; then
		CR "pkg delete -y -f gcc47\* || true"
	else
		CR "pkg_delete -f gcc47\* || true"
	fi

	echo "Restoring gcc47 libraries"
	for f in $files_to_save
	do
		CR "mv $f.bak $f"
	done
}

# This is a hack.
# I don't know if it's necessary to save the files, a la
# remove_gcc47.
# grub added a dependency for gcc, which resulted in gcc46.
remove_gcc()
{
	local files_to_save="
/usr/local/lib/gcc47/libstdc++.so.6
/usr/local/lib/gcc47/libstdc++.so
/usr/local/lib/gcc47/libstdc++.a
/usr/local/lib/gcc47/libmudflap.so.0
/usr/local/lib/gcc47/libmudflap.so
/usr/local/lib/gcc47/libmudflapth.so.0
/usr/local/lib/gcc47/libmudflapth.so
/usr/local/lib/gcc47/libssp.so.0
/usr/local/lib/gcc47/libssp.so
/usr/local/lib/gcc47/libgcc_s.so.1
/usr/local/lib/gcc47/libgcc_s.so
/usr/local/lib/gcc47/libquadmath.so.0
/usr/local/lib/gcc47/libquadmath.so
/usr/local/lib/gcc47/libquadmath.a
/usr/local/lib/gcc47/libgomp.spec
/usr/local/lib/gcc47/libgomp.so.1
/usr/local/lib/gcc47/libgomp.so
/usr/local/lib/gcc47/libitm.spec
/usr/local/lib/gcc47/libitm.so.1
/usr/local/lib/gcc47/libitm.so
/usr/local/libdata/ldconfig/gcc47
	"

	echo "Backing up gcc47 libraries"
	for f in $files_to_save
	do
		CR "mv $f $f.bak"
	done
	echo "Removing gcc" 
	if [ -n "$WITH_PKGNG" ]; then
		CR "pkg delete -y -f gcc\* || true"
	else
		CR "pkg_delete -f gcc\* || true"
	fi

	echo "Restoring gcc47 libraries"
	for f in $files_to_save
	do
		CR "mv $f.bak $f"
	done
}

remove_packages()
{
	# Workaround to remove packages from a fat image
	local pkg_to_remove

	for pkg_to_remove in gcc-ecj kBuild cmake docbook \
                             automake autoconf
	do
		echo "Removing $pkg_to_remove"
		if [ -n "$WITH_PKGNG" ]; then
			CR "pkg delete -y -f $pkg_to_remove\* || true"
		else
			CR "pkg_delete -f $pkg_to_remove\* || true"
		fi
	done
}

remove_var_cache_pkg()
{
	if [ -n "$WITH_PKGNG" ]; then
		CR "pkg clean -a -y"
	fi
	# Revisit the thing below later
# 	# And now remove the package database
# 	echo "Removing pkg package"
# 	if [ -n "$WITH_PKGNG" ]; then
# 		CR "pkg delete -y -f pkg\* || true"
# 		CR "rm -rf var/db/pkg || true"
# 	else
# 		CR "pkg_delete -f pkg\* || true"
# 	fi
}

create_var_home_symlink()
{
	# Create a link to a non-persistent location that ix-activedirectory
	# and ix-ldap can use as a pointer to a home directory on persistent
	# storage (/mnt/tank/homes, etc).
	rm -f $NANO_WORLDDIR/home || :
	rm -Rf $NANO_WORLDDIR/home
	ln -sfh /var/home $NANO_WORLDDIR/home
}

freenas_custom()
{
	compress_ko()
	{
# XXX: If we want to Dtrace the kernel it cannot be compressed
#		if [ -f ${NANO_WORLDDIR}/boot/kernel/$1 ]; then
#			gzip -v9 ${NANO_WORLDDIR}/boot/kernel/$1
#		fi
	}

	# Compress the kernel and preloaded modules
	compress_ko kernel
	compress_ko fuse.ko
	compress_ko geom_mirror.ko
	compress_ko geom_stripe.ko
	compress_ko geom_raid3.ko
	compress_ko geom_gate.ko

	# nuke .pyo files
	find ${NANO_WORLDDIR}/usr/local -name '*.pyo' | xargs rm -f

	# kill includes (saves 14MB)
	find ${NANO_WORLDDIR}/usr/local/include \! -name 'pyconfig.h' -type f | xargs rm -f

	# kill docs (saves 22MB)
	rm -rf ${NANO_WORLDDIR}/usr/local/share/doc
	rm -rf ${NANO_WORLDDIR}/usr/local/share/gtk-doc

	# kill gobject introspection xml
	rm -rf ${NANO_WORLDDIR}/usr/local/share/gir-1.0

	# and info (2MB)
	rm -rf ${NANO_WORLDDIR}/usr/local/info

	# and examples (1.7M)
	rm -rf ${NANO_WORLDDIR}/usr/local/share/examples

	# for now just remove the following file (later on revisit remove_var_cache_pkg)
	rm -rf ${NANO_WORLDDIR}/etc/local/periodic/security
	rm -rf ${NANO_WORLDDIR}/conf/base/etc/local/periodic/security

	# Kill all .a's and .la's that are installed (20MB+)
	find ${NANO_WORLDDIR} -name \*.a -or -name \*.la -delete

	# magic.mgc is just a speed optimization.  Kill it for 1.7MB
	rm -f ${NANO_WORLDDIR}/usr/share/misc/magic.mgc

	# strip binaries (saves spaces on non-debug images).
	if [ "${DEBUG}" != 1 ]; then
		pprint 4 "Stripping binaries and libraries"
		for dir in $(find ${NANO_WORLDDIR}/usr/local -name '*bin' -or -name 'libexec' -maxdepth 3); do
			for f in $(find $dir -type f); do
				if ! dontstrip "$f"
				then
					strip 2>/dev/null $f || :
				fi
			done
		done
		# .so's are the only thing that need to be stripped. The rest
		# should remain untouched.
		for f in $(find ${NANO_WORLDDIR}/usr/local/lib -name '*.so' -or -name '*.so.*' -maxdepth 3); do
			if ! dontstrip "$f"
			then
				strip 2>/dev/null $f || :
			fi
		done
	fi

	# We dont need proftpd blacklist.dat.sample, takes up too much space in /etc
	rm -f ${NANO_WORLDDIR}/conf/base/etc/local/proftpd/blacklist.dat.sample

	# Last second tweaks
	chown -R root:wheel ${NANO_WORLDDIR}/root
	chmod 0755 ${NANO_WORLDDIR}/root/*
	chmod 0755 ${NANO_WORLDDIR}/*
	chmod 0440 ${NANO_WORLDDIR}/usr/local/etc/sudoers
	chown -R root:wheel ${NANO_WORLDDIR}/etc
	chown -R root:wheel ${NANO_WORLDDIR}/boot
	chown root:wheel ${NANO_WORLDDIR}/
	chown root:wheel ${NANO_WORLDDIR}/usr
	find ${NANO_WORLDDIR} -type f -name "*~" -delete
	find ${NANO_WORLDDIR}/usr/local -type f -name "*.po" -delete
	find ${NANO_WORLDDIR} -type f -name "*.service" -delete
	mkdir -p ${NANO_WORLDDIR}/data/zfs
	ln -s -f /usr/local/bin/bash ${NANO_WORLDDIR}/bin/bash
	ln -s -f /data/zfs/zpool.cache ${NANO_WORLDDIR}/boot/zfs/zpool.cache

	# This is wrong.  Needs a way to tell kernel how to find the mount utility
	# instead.
	if [ "$FREEBSD_RELEASE_MAJOR_VERSION" -lt 10 ]; then
		mv ${NANO_WORLDDIR}/sbin/mount_ntfs ${NANO_WORLDDIR}/sbin/mount_ntfs-kern
	fi
	ln -s -f /usr/local/bin/ntfs-3g ${NANO_WORLDDIR}/sbin/mount_ntfs

}

last_orders() {
	local cd_image_log
	local gui_upgrade_bname gui_upgrade_image_log
	local vmdk_image vmdk_image_compressed vmdk_image_log

	cd_image_log="${MAKEOBJDIRPREFIX}/_.cd_iso"
	gui_image_log="${MAKEOBJDIRPREFIX}/_.gui_image"
	vmdk_image_log="${MAKEOBJDIRPREFIX}/_.vmdk_image"

	gui_upgrade_bname="$NANO_DISKIMGDIR/$NANO_IMGNAME.GUI_Upgrade"
	vmdk_image="$NANO_DISKIMGDIR/$NANO_IMGNAME.vmdk"
	vmdk_image_compressed="$NANO_DISKIMGDIR/$NANO_IMGNAME.vmdk.xz"


	pprint 2 "Creating ISO image"
	log_file "${cd_image_log}"

	(
	set -x

	sh "$AVATAR_ROOT/build/create_iso.sh"

	) > "${cd_image_log}" 2>&1
	if $do_copyout_partition; then

		pprint 2 "Compressing GUI upgrade image"
		log_file "${gui_image_log}"

		(
		set -x

		# the -s arguments map root's "update*" files into the
		# gui image's bin directory.

		if is_truenas ; then
			tar -c -p -f ${NANO_OBJ}/gui-boot.tar \
				-C ${NANO_OBJ}/_.isodir ./boot
			tar -c -p -f ${NANO_OBJ}/gui-install-environment.tar \
				-C ${NANO_OBJ}/_.instufs .
			tar -c -p -f ${NANO_OBJ}/gui-packages.tar \
				-s '@^Packages@FreeNAS/Packages@' \
				-C ${NANO_OBJ}/_.packages .
			tar -c -p -v -f ${gui_upgrade_bname}.tar \
				-s '@^update$@bin/update@' \
				-s '@^updatep1$@bin/updatep1@' \
				-s '@^updatep2$@bin/updatep2@' \
				-C "$NANO_WORLDDIR" \
					etc/avatar.conf \
				-C "${AVATAR_ROOT}/build/nanobsd-cfg/Installer" \
					. \
				-C "${TRUENAS_COMPONENTS_ROOT}/nanobsd/Installer" \
					. \
				-C "$AVATAR_ROOT/build/nanobsd-cfg/GUI_Upgrade" \
					. \
				-C "${NANO_OBJ}" \
					gui-boot.tar \
					gui-install-environment.tar \
					gui-packages.tar
				${NANO_XZ} ${PXZ_ACCEL} -9 -z ${gui_upgrade_bname}.tar
				mv ${gui_upgrade_bname}.tar.xz ${gui_upgrade_bname}.txz
		else
		    	tar -c -p -f ${NANO_OBJ}/gui-boot.tar \
			    	-C ${NANO_OBJ}/_.isodir ./boot
			tar -c -p -f ${NANO_OBJ}/gui-install-environment.tar \
			    	-C ${NANO_OBJ}/_.instufs .
			tar -c -p -f ${NANO_OBJ}/gui-packages.tar \
			    	-s '@^Packages@FreeNAS/Packages@' \
				-C ${NANO_OBJ}/_.packages .
			tar -c -p -v -f ${gui_upgrade_bname}.tar \
				-s '@^update$@bin/update@' \
				-s '@^updatep1$@bin/updatep1@' \
				-s '@^updatep2$@bin/updatep2@' \
				-C "$NANO_WORLDDIR" \
					etc/avatar.conf \
				-C "$AVATAR_ROOT/build/nanobsd-cfg/Installer" \
					. \
				-C "$AVATAR_ROOT/build/nanobsd-cfg/GUI_Upgrade" \
					. \
			    	-C "${NANO_OBJ}" \
					gui-boot.tar \
			    		gui-install-environment.tar \
					gui-packages.tar
			${NANO_XZ} ${PXZ_ACCEL} -9 -z ${gui_upgrade_bname}.tar
			mv ${gui_upgrade_bname}.tar.xz ${gui_upgrade_bname}.txz
			rm -f ${NANO_OBJ}/gui-boot.tar ${NANO_OBJ}/gui-install-environment.tar
			rm -f ${NANO_OBJ}/gui-packages.tar
		fi
		) > "${gui_image_log}" 2>&1
		(
		cd $NANO_DISKIMGDIR
		sha256_signature=`sha256 ${NANO_IMGNAME}.GUI_Upgrade.txz`
		echo "${sha256_signature}" > ${NANO_IMGNAME}.GUI_Upgrade.txz.sha256.txt
		)
	fi

}


build_kernel2 ( ) (
	local _kernel=$1
	if [ -z "$1" ] ; then
		_kernel=${NANO_KERNEL}
	fi
	local _logfile="${MAKEOBJDIRPREFIX}/_.bk_$(basename ${_kernel})"

	pprint 2 "build kernel ($_kernel)"
	log_file "${_logfile}"

	(
	if [ -f ${_kernel} ] ; then
		kernconfdir=$(realpath $(dirname ${_kernel}))
		kernconf=$(basename ${_kernel})
	else
		kernconf=${_kernel}
	fi

	cd ${NANO_SRC};
	# unset these just in case to avoid compiler complaints
	# when cross-building
	unset TARGET_CPUTYPE
	unset TARGET_BIG_ENDIAN
	# Note: We intentionally build all modules, not only the ones in
	# NANO_MODULES so the built world can be reused by multiple images.
	env \
		TARGET=${NANO_ARCH%:*} \
		TARGET_ARCH=${NANO_ARCH##*:} \
		${NANO_PMAKE} \
		buildkernel NO_KERNELCLEAN=1 \
		${kernconfdir:+"KERNCONFDIR="}${kernconfdir} \
		KERNCONF=${kernconf} \
		MODULES_OVERRIDE="${NANO_MODULES}" \
		SRCCONF=${SRCCONF} \
		__MAKE_CONF=${NANO_MAKE_CONF_BUILD} \
	) > ${_logfile} 2>&1
)

install_kernel2 ( ) (
	local _kernel=$1
	local _kodir=$2

	if [ -z "$1" ] ; then
		_kernel=${NANO_KERNEL}
	fi
	if [ -z "$2" ] ; then
		_kodir=/boot/kernel
	fi

	local _logfile="${NANO_OBJ}/_.ik_$(basename ${_kernel})"
	pprint 2 "install kernel ($_kernel)"
	log_file "${_logfile}"

	(
	if [ -f ${_kernel} ] ; then
		kernconfdir=$(realpath $(dirname ${_kernel}))
		kernconf=$(basename ${_kernel})
	else
		kernconf=${_kernel}
	fi

	cd ${NANO_SRC}
	env \
		TARGET=${NANO_ARCH%:*} \
		TARGET_ARCH=${NANO_ARCH##*:} \
		${NANO_PMAKE} \
		installkernel \
		INSTALL_NODEBUG= \
		DESTDIR=${NANO_WORLDDIR} \
		${kernconfdir:+"KERNCONFDIR="}${kernconfdir} \
		KERNCONF=${kernconf} \
		KODIR=${_kodir} \
		MODULES_OVERRIDE="${NANO_MODULES}"
		SRCCONF=${SRCCONF} \
		__MAKE_CONF=${NANO_MAKE_CONF_INSTALL} \
	) > ${_logfile} 2>&1
)

build_debug_kernel ( ) 
{
	local _kernconfdir=$(dirname ${NANO_KERNEL})
	local _kernconf=$(basename ${NANO_KERNEL})

	(
	cd ${_kernconfdir}
	cat $_kernconf $NANO_CFG_BASE/DEBUG > ${NANO_OBJ}/${_kernconf}-DEBUG
	)

	build_kernel2 ${NANO_OBJ}/${_kernconf}-DEBUG /boot/kernel-debug
}

install_debug_kernel ( )
{
	local _kernconf=$(basename ${NANO_KERNEL})

	install_kernel2  ${NANO_OBJ}/${_kernconf}-DEBUG  /boot/kernel-debug
}

clean_etc()
{
	rm -f ${NANO_WORLDDIR}/etc/fstab ${NANO_WORLDDIR}/conf/base/etc/fstab
}

install_ports()
{
	local install_info_hack=0
	if [ ! -e ${NANO_WORLDDIR}/usr/bin/install-info ]; then
		touch ${NANO_WORLDDIR}/usr/bin/install-info
		chmod +x ${NANO_WORLDDIR}/usr/bin/install-info
		install_info_hack=1
	fi

	${AVATAR_ROOT}/build/ports/install-ports.sh

	if [ $install_info_hack -eq 1 ]; then
		rm -f ${NANO_WORLDDIR}/usr/bin/install-info
	fi

	# Workaround until pkg bug: https://github.com/freebsd/pkg/issues/857
	# is fixed to detect errors in pkg-install scripts
	ls ${NANO_WORLDDIR}/data/freenas-v1.db ${NANO_WORLDDIR}/data/factory-v1.db

	
}
