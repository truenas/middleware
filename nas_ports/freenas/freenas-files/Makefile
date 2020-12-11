# $FreeBSD$

PORTNAME=	freenas-files
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	miscellaneous files for FreeNAS

PREFIX=/

USES= 	python
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}snmp_passpersist>=1.3.0:net-mgmt/py-snmp_passpersist \
		${PYTHON_PKGNAMEPREFIX}middlewared>0:freenas/py-middlewared@${PY_FLAVOR} \
		firmware>0:freenas/firmware

# explicitly set this for the port build
FREEBSD_SRCTOP=/usr/src
PLIST_SUB=	MACHINE_ARCH=${MACHINE_ARCH}

EXTRACT_ONLY=
WRKSRC=/usr/nas_source

SUB_FILES=	pkg-install

# no checksum, we just used git!
checksum fetch:
	echo ${.TARGET} not needed because building direct

pre-clean:
	@

ALL_TARGET=obj all

MAKE_JOBS_UNSAFE=yes

.include <bsd.port.pre.mk>

do-build:
	${MAKE} -C ${WRKSRC}/winacl   obj
	${MAKE} -C ${WRKSRC}/winacl  all


do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/bin
	mkdir -p ${STAGEDIR}${PREFIX}/usr/sbin
	mkdir -p ${STAGEDIR}${PREFIX}/usr/share/man/man8
	mkdir -p ${STAGEDIR}${PREFIX}/boot/modules
.if defined(DEBUG_FLAGS)
	mkdir -p ${STAGEDIR}${DEBUGDIR}${PREFIX}/boot/modules
.endif
	${MAKE} -C ${WRKSRC}/winacl DESTDIR=${STAGEDIR} BINDIR=${PREFIX}/usr/local/bin install
	#
	# Adding autotune
	#
	${INSTALL_SCRIPT} ${WRKSRC}/autotune/files/autotune.py ${STAGEDIR}${PREFIX}/usr/local/bin/autotune
	${INSTALL_SCRIPT} ${WRKSRC}/afpusers/files/afpusers.py ${STAGEDIR}${PREFIX}/usr/local/bin/afpusers
	#
	#
	${CP} -a ${WRKSRC}/freenas/ ${STAGEDIR}/
	${MV} ${STAGEDIR}/usr/local/bin.freebsd/* ${STAGEDIR}/usr/local/bin/
	${RM} -rf ${STAGEDIR}/usr/local/bin.freebsd
	${MV} ${STAGEDIR}/usr/local/sbin.freebsd/* ${STAGEDIR}/usr/local/sbin/
	${RM} -rf ${STAGEDIR}/usr/local/sbin.freebsd
	(cd ${STAGEDIR}; ${FIND} . \( -type f -o -type l \) \
		| ${GREP} -v "/debian/" \
		| ${GREP} -v "/netcli.sh" \
		| ${GREP} -v "/systemd/" \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| ${AWK} '{$$1=""; sub(/^[ \t]+/, ""); print $$0}' >> ${TMPPLIST})

.include <bsd.port.post.mk>
