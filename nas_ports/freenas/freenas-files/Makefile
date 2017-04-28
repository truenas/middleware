# $FreeBSD$

PORTNAME=	freenas-files
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	miscellaneous files for FreeNAS

PRODUCT?=
PREFIX=/

USES= 	python
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}snmp_passpersist>=1.3.0:net-mgmt/py-snmp_passpersist

# explicitly set this for the port build
FREEBSD_SRCTOP=/usr/src
PLIST_SUB=	MACHINE_ARCH=${MACHINE_ARCH}

EXTRACT_ONLY=
WRKSRC=/usr/nas_source

# no checksum, we just used git!
checksum fetch:
	echo ${.TARGET} not needed because building direct

pre-clean:
	@

ALL_TARGET=obj all

MAKE_JOBS_UNSAFE=yes

.include <bsd.port.pre.mk>

do-build:
	${MAKE} -C ${WRKSRC}/extract-tarball   obj
	${MAKE} -C ${WRKSRC}/extract-tarball  all
	${MAKE} -C ${WRKSRC}/freenas-sysctl obj
	${MAKE} -C ${WRKSRC}/freenas-sysctl all
	${MAKE} -C ${WRKSRC}/winacl   obj
	${MAKE} -C ${WRKSRC}/winacl  all

do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/bin
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/bin/freenas-snmp
	mkdir -p ${STAGEDIR}${PREFIX}/boot/modules

	${MAKE} -C ${WRKSRC}/extract-tarball  BINDIR=${STAGEDIR}${PREFIX}/usr/local/bin install
	${MAKE} -C ${WRKSRC}/winacl  BINDIR=${STAGEDIR}${PREFIX}/usr/local/bin install
	${MAKE} -C ${WRKSRC}/freenas-sysctl KMODDIR=${STAGEDIR}${PREFIX}/boot/modules install
	#
	# Adding autotune
	#
	${INSTALL_SCRIPT} ${WRKSRC}/autotune/files/autotune.py ${STAGEDIR}${PREFIX}/usr/local/bin/autotune
	${INSTALL_SCRIPT} ${WRKSRC}/afpusers/files/afpusers.py ${STAGEDIR}${PREFIX}/usr/local/bin/afpusers
	#
	#
	${CP} -a ${WRKSRC}/freenas/ ${STAGEDIR}/
.if ${PRODUCT} == "TrueNAS"
	${RM} \
		${STAGEDIR}/boot/loader.conf \
		${STAGEDIR}/boot/loader.rc.local \
		${STAGEDIR}/etc/sysctl.conf \
		${STAGEDIR}/etc/pf.conf.block \
		${STAGEDIR}/etc/motd \
		${STAGEDIR}/etc/ix.rc.d/ix_pf_early \
		${STAGEDIR}/etc/ix.rc.d/ix_pf_late
.endif
	(cd ${STAGEDIR}; ${FIND} . \( -type f -o -type l \) \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| ${AWK} '{print $$2 }' >> ${TMPPLIST})

.include <bsd.port.post.mk>
