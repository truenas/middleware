.include <bsd.own.mk>

.include "Makefile.inc"

SUBDIR= create_manifest \
	create_package \
	diff_packages \
	freenas-install \
	lib \
	manifest_util \
	pkgify \
	freenas-update \
	freenas-release \
	verify_signature \
	certificates

beforeinstall:
	${INSTALL} -d ${DESTDIR}${BINDIR}
	${INSTALL} -d ${DESTDIR}${LIBDIR}

.include <bsd.subdir.mk>

PORTNAME=	freenas-pkgtools
PORTVERSION=	0.0.1
PORTREVISION=	1
CATEGORIES= sysutils
MAINTAINER=	dev@ixsystems.com
COMMENT=	FreeNAS package tools
LIB_DEPENDS=	libsqlite3.so:${PORTSDIR}/databases/sqlite3 \
		libopenssl.so libcrypto.so
USE_PYTHON=     yes
USE_OPENSSL=	yes

.ORDER:	install package

# Create a package from the install
# Since we just installed the tools we need,
# we use them.
# Note that this requires python and various
# other packages to be installed on the system.

.if defined(VERSION) && defined(REVISION)
MVERSION=	${VERSION}-${REVISION}
.elif defined(VERSION)
MVERSION=	${VERSION}
.elif defined(REVISION)
MVERSION=	${REVISION}
.else
MVERSION=	1
.endif

ROOTDIR= ${DESTDIR}${BINDIR:S/usr\/local\/bin//}

.if !defined(PACKAGE_DIR)
PACKAGE_DIR=	/tmp/Packages
.endif

# This creates a package to be installed
# on FreeNAS.  "make install" will add more
# files.

package: install
	mkdir -p ${PACKAGE_DIR}
	sed -e 's/VERSION/${MVERSION}/' < ${.CURDIR}/files/+MANIFEST > ${.OBJDIR}/+MANIFEST
	/usr/sbin/pkg create -o ${PACKAGE_DIR} -p ${.CURDIR}/files/pkg-plist -r ${ROOTDIR} -m ${.OBJDIR} -f tgz
