#
# $FreeBSD$
# $Id$
#

PORTNAME=       freenas-files
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        miscellaneous files for FreeNAS

USE_XZ=		yes

PREFIX=/

# explicitly set this for the port build
FREEBSD_SRCTOP=/usr/src
PLIST_SUB=	MACHINE_ARCH=${MACHINE_ARCH}

EXTRACT_ONLY=
WRKSRC=/usr/freenas_src

# no checksum, we just used git!
 #extract:
checksum fetch:
	echo ${.TARGET} not needed because building direct

pre-clean:
	@

ALL_TARGET=obj all

MAKE_JOBS_UNSAFE=yes

do-build:
	${MAKE} -C ${WRKSRC}/extract-tarball   obj
	${MAKE} -C ${WRKSRC}/extract-tarball  all
	${MAKE} -C ${WRKSRC}/winacl   obj
	${MAKE} -C ${WRKSRC}/winacl  all
	${MAKE} -C ${WRKSRC}/freenas-pkgtools obj
	${MAKE} -C ${WRKSRC}/freenas-pkgtools all

do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/boot
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/bin
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/etc
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/lib/freenasOS
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/libexec
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/sbin
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/libexec/samba
	${MAKE} -C ${WRKSRC}/extract-tarball  BINDIR=${STAGEDIR}${PREFIX}/usr/local/bin install
	${MAKE} -C ${WRKSRC}/winacl  BINDIR=${STAGEDIR}${PREFIX}/usr/local/bin install
	${MAKE} -C ${WRKSRC}/freenas-pkgtools BINDIR=${STAGEDIR}${PREFIX}/usr/local/bin LIBDIR=${STAGEDIR}${PREFIX}/usr/local/lib/freenasOS install
	#
	# Adding autotune
	#
	${INSTALL_SCRIPT} ${WRKSRC}/autotune/files/autotune.py ${STAGEDIR}${PREFIX}/usr/local/bin/autotune
	${INSTALL_SCRIPT} ${WRKSRC}/afpusers/files/afpusers.py ${STAGEDIR}${PREFIX}/usr/local/bin/afpusers
	#
	#
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/arc_summary.py ${STAGEDIR}/${PREFIX}/usr/local/bin/arc_summary.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/arcstat.py ${STAGEDIR}/${PREFIX}/usr/local/bin/arcstat.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/crashuploader ${STAGEDIR}/${PREFIX}/usr/local/bin/crashuploader
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/custom-upssched-cmd ${STAGEDIR}/${PREFIX}/usr/local/bin/custom-upssched-cmd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/freenas-debug ${STAGEDIR}/${PREFIX}/usr/local/bin/freenas-debug
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/ixdiagnose ${STAGEDIR}/${PREFIX}/usr/local/bin/ixdiagnose
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/mfistatus.py ${STAGEDIR}/${PREFIX}/usr/local/bin/mfistatus.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/perftests-nas ${STAGEDIR}/${PREFIX}/usr/local/bin/perftests-nas
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/zilstat ${STAGEDIR}/${PREFIX}/usr/local/bin/zilstat
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/adtool ${STAGEDIR}/${PREFIX}/usr/local/bin/adtool
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/etc/avahi
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/avahi/avahi-daemon.conf ${STAGEDIR}/${PREFIX}/usr/local/etc/avahi/avahi-daemon.conf
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/etc/nginx
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/samba.gdb ${STAGEDIR}/${PREFIX}/usr/local/etc/samba.gdb
	${INSTALL_DATA} ${WRKSRC}/freenas/usr/local/etc/sudoers ${STAGEDIR}/${PREFIX}/usr/local/etc/sudoers
	${INSTALL_DATA} ${WRKSRC}/freenas/usr/local/etc/appcafe.conf ${STAGEDIR}/${PREFIX}/usr/local/etc/appcafe.conf
	${INSTALL_DATA} ${WRKSRC}/freenas/usr/local/etc/warden.conf ${STAGEDIR}/${PREFIX}/usr/local/etc/warden.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/samba/samba-backtrace ${STAGEDIR}/${PREFIX}/usr/local/libexec/samba/samba-backtrace
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/sbin/sas2flash ${STAGEDIR}/${PREFIX}/usr/local/sbin/sas2flash
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/sbin/save_rrds.sh ${STAGEDIR}/${PREFIX}/usr/local/sbin/save_rrds.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/sbin/scrub ${STAGEDIR}/${PREFIX}/usr/local/sbin/scrub
	${MKDIR} ${STAGEDIR}${PREFIX}/usr/local/share/perftests-nas/tests
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/perftests-nas/tests/* ${STAGEDIR}${PREFIX}/usr/local/share/perftests-nas/tests/
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/www/data
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/rc.subr ${STAGEDIR}/${PREFIX}/etc/rc.subr
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/rc.d/cleanvar ${STAGEDIR}/${PREFIX}/etc/rc.d/cleanvar
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/rc.d/ix-bootstrap ${STAGEDIR}/${PREFIX}/etc/rc.d/ix-bootstrap
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/rc.d/ix-etc ${STAGEDIR}/${PREFIX}/etc/rc.d/ix-etc
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/rc.d/ix-network ${STAGEDIR}/${PREFIX}/etc/rc.d/ix-network

	ln -s /usr/local/etc ${STAGEDIR}${PREFIX}/etc/local
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/boot/loader.conf ${STAGEDIR}${PREFIX}/boot/loader.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/csh.cshrc ${STAGEDIR}${PREFIX}/etc/csh.cshrc
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/devfs.rules ${STAGEDIR}${PREFIX}/etc/devfs.rules
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/exports ${STAGEDIR}${PREFIX}/etc/exports
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/freenas.conf ${STAGEDIR}${PREFIX}/etc/freenas.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/gettytab ${STAGEDIR}${PREFIX}/etc/gettytab
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ipfw.conf.block ${STAGEDIR}${PREFIX}/etc/ipfw.conf.block
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/newsyslog.conf ${STAGEDIR}${PREFIX}/etc/newsyslog.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/pf.conf.block ${STAGEDIR}${PREFIX}/etc/pf.conf.block
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/pw.conf ${STAGEDIR}${PREFIX}/etc/pw.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/rc.conf ${STAGEDIR}${PREFIX}/etc/rc.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/sysctl.conf ${STAGEDIR}${PREFIX}/etc/sysctl.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ttys ${STAGEDIR}${PREFIX}/etc/ttys
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/root/.bashrc ${STAGEDIR}${PREFIX}/.bashrc
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/root/.cshrc ${STAGEDIR}${PREFIX}/.cshrc
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/root/.profile ${STAGEDIR}${PREFIX}/.profile
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/root/.shrc ${STAGEDIR}${PREFIX}/.shrc


.include <bsd.port.mk>
