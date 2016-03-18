# Makefile for freenas zfsd "port"

PORTNAME=       zfsd
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=   ${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        zfsd from FreeBSD project imported to FreeNAS

BUNDLED_LIBS=	yes
USES_LDCONFIG=	yes

PREFIX=/

# explicitly set this for the port build
FREEBSD_SRCTOP=/usr/src
PLIST_SUB=	MACHINE_ARCH=${MACHINE_ARCH}

EXTRACT_ONLY=
WRKSRC?=/usr/nas_source/zfsd

checksum fetch:
	echo ${.TARGET} not needed because building direct

pre-clean:
	@

ALL_TARGET=obj all

# Must install library (in build jail's /usr/lib)
# so that we can build zfsd.
#
# We pass SRCDIR=/usr/src to override zfsd's attempt to
# work relative to the port.
do-build:
	${MAKE} -C ${WRKSRC}/head/lib/libdevdctl obj
	# install shared library and run ldconfig on it
	${MAKE} -C ${WRKSRC}/head/lib/libdevdctl depend all
	${MKDIR} -p -m 0755 /usr/include/devctl
	${MKDIR} -p -m 0755 /usr/lib
	${MAKE} -C ${WRKSRC}/head/lib/libdevdctl install
	/sbin/ldconfig -m
	${MAKE} -C ${WRKSRC}/head/cddl/sbin/zfsd obj
	${MAKE} -C ${WRKSRC}/head/cddl/sbin/zfsd SRCDIR=/usr/src depend
	${MAKE} -C ${WRKSRC}/head/cddl/sbin/zfsd SRCDIR=/usr/src all

# This time, install shared library into stage dir.
do-install:
	${MKDIR} -p -m 0755 ${STAGEDIR}${PREFIX}/usr/include/devctl
	${MKDIR} -p -m 0755 ${STAGEDIR}${PREFIX}/usr/lib
	${MAKE} -C ${WRKSRC}/head/lib/libdevdctl \
	    DESTDIR=${STAGEDIR}${PREFIX} install
	${INSTALL_SCRIPT} \
	    ${WRKSRC}/head/etc/rc.d/zfsd \
	    ${STAGEDIR}${PREFIX}/etc/rc.d/zfsd
	${MKDIR} -p -m 0755 ${STAGEDIR}${PREFIX}/etc/zfs
	${MKDIR} -p -m 0755 ${STAGEDIR}${PREFIX}/data/zfs/cases
	${INSTALL} -l s ../../data/zfs/cases \
	    ${STAGEDIR}${PREFIX}/etc/zfs/cases
	${MAKE} -C ${WRKSRC}/head/cddl/sbin/zfsd DESTDIR=${STAGEDIR}${PREFIX} \
	    install

.include <bsd.port.mk>
