# Created by: Dirk Froemberg <dirk@FreeBSD.org>
# $FreeBSD: head/security/openssl/Makefile 424879 2016-10-28 20:05:48Z brnrd $

PORTNAME=	openssl
PORTVERSION=	1.0.2j
PORTREVISION=	1
PORTEPOCH=	1
CATEGORIES=	security devel
MASTER_SITES=	http://www.openssl.org/source/ \
		ftp://ftp.cert.dfn.de/pub/tools/net/openssl/source/
DIST_SUBDIR=	${DISTNAME}

MAINTAINER=	brnrd@FreeBSD.org
COMMENT=	SSL and crypto library

LICENSE=	OpenSSL
LICENSE_FILE=	${WRKSRC}/LICENSE

CONFLICTS_INSTALL=	libressl-[0-9]* \
			libressl-devel-[0-9]* \
			openssl-devel-[0-9]*

OPTIONS_DEFINE=		DOCS MAN3 PADLOCK RFC3779 SHARED THREADS ZLIB
OPTIONS_DEFAULT=	SHARED THREADS SSE2 SCTP SSL2 SSL3 MD2 MAN3
OPTIONS_DEFINE_amd64=	EC
OPTIONS_DEFAULT_amd64=	EC
OPTIONS_DEFINE_ia64=	EC
OPTIONS_DEFAULT_ia64=	EC
TARGET_ARCH?=	${MACHINE_ARCH}
.if ${TARGET_ARCH} == "mips64el"
OPTIONS_DEFINE_mips=	EC
OPTIONS_DEFAULT_mips=	EC
.endif
OPTIONS_GROUP=	CIPHERS HASHES OPTIMIZE PROTOCOLS
OPTIONS_GROUP_CIPHERS=	EXPCIPHERS RC5 
OPTIONS_GROUP_HASHES=	MD2
OPTIONS_GROUP_OPTIMIZE=	ASM SSE2
OPTIONS_GROUP_PROTOCOLS=	SCTP SSL2 SSL3
.if ${TARGET_ARCH} == "i386"
OPTIONS_GROUP_OPTIMIZE+=	I386
.endif
OPTIONS_SUB=	yes
ASM_DESC=	Optimized Assembler code
CIPHERS_DESC=	Cipher Suite support
EC_DESC=	Optimize NIST elliptic curves
EXPCIPHERS_DESC=	Include experimental ciphers
HASHES_DESC=	Hash Function Support
I386_DESC=	Optimize for i386 (instead of i486+)
MAN3_DESC=	Install API manpages (section 3)
MD2_DESC=	MD2 hash (obsolete)
OPTIMIZE_DESC=	Optimizations
PADLOCK_DESC=	VIA Padlock support
PROTOCOLS_DESC=	Protocol Support
RC5_DESC=	RC5 cipher (patented)
RFC3779_DESC=	RFC3779 support (BGP)
SCTP_DESC=	SCTP protocol support
SHARED_DESC=	Build shared libs
SSE2_DESC=	Runtime SSE2 detection
SSL2_DESC=	SSLv2 protocol support
SSL3_DESC=	SSLv3 protocol support
ZLIB_DESC=	zlib compression support

USES=		cpe perl5
USE_PERL5=	build
MAKE_ARGS+=	WHOLE_ARCHIVE_FLAG=--whole-archive
MAKE_ENV+=	LIBRPATH="${PREFIX}/lib" GREP_OPTIONS=
SUB_FILES=	pkg-message

MAKE_JOBS_UNSAFE=	yes

ASM_CONFIGURE_OFF=	no-asm
EC_CONFIGURE_ON=	enable-ec_nistp_64_gcc_128
EC_CONFIGURE_OFF=	no-ec_nistp_64_gcc_128
I386_CONFIGURE_ON=	386
MD2_CONFIGURE_ON=	enable-md2
MD2_CONFIGURE_OFF=	no-md2
PADLOCK_PATCH_SITES=	http://git.alpinelinux.org/cgit/aports/plain/main/openssl/:padlock
PADLOCK_PATCHFILES=	1001-crypto-hmac-support-EVP_MD_CTX_FLAG_ONESHOT-and-set-.patch:padlock \
			1002-backport-changes-from-upstream-padlock-module.patch:padlock \
			1003-engines-e_padlock-implement-sha1-sha224-sha256-accel.patch:padlock \
			1004-crypto-engine-autoload-padlock-dynamic-engine.patch:padlock
PADLOCK_VARS=		PATCH_DIST_STRIP=-p1
RC5_CONFIGURE_ON=	enable-rc5
RC5_CONFIGURE_OFF=	no-rc5
RFC3779_CONFIGURE_ON=	enable-rfc3779
RFC3779_CONFIGURE_OFF=	no-rfc3779
SCTP_CONFIGURE_ON=	sctp
SCTP_CONFIGURE_OFF=	no-sctp
SHARED_CONFIGURE_ON=	shared
SHARED_MAKE_ENV=	SHLIBVER=${OPENSSL_SHLIBVER}
SHARED_PLIST_SUB=	SHLIBVER=${OPENSSL_SHLIBVER}
SHARED_USE=		ldconfig=yes
SSE2_CONFIGURE_OFF=	no-sse2
SSL2_CONFIGURE_ON=	enable-ssl2
SSL2_CONFIGURE_OFF=	no-ssl2
SSL3_CONFIGURE_ON=	enable-ssl3
SSL3_CONFIGURE_OFF=	no-ssl3 no-ssl3-method
THREADS_CONFIGURE_ON=	threads
THREADS_CONFIGURE_OFF=	no-threads
ZLIB_CONFIGURE_ON=	zlib zlib-dynamic
ZLIB_CONFIGURE_OFF=	no-zlib no-zlib-dynamic

.include <bsd.port.pre.mk>

.if ${PREFIX} == /usr
IGNORE=	the OpenSSL port can not be installed over the base version
.endif

OPENSSLDIR?=	${PREFIX}/openssl
PLIST_SUB+=	OPENSSLDIR=${OPENSSLDIR:S=^${PREFIX}/==}

.include "version.mk"

.if ${PORT_OPTIONS:MASM}
BROKEN_sparc64=		option ASM generates illegal instructions
.endif

CONFIGURE_ARGS+=	no-gmp

post-patch:
	${REINPLACE_CMD} -e 's|m4 -B 8192|m4|g' \
		${WRKSRC}/crypto/des/Makefile
	${REINPLACE_CMD} -e 's|SHLIB_VERSION_NUMBER "1.0.0"|SHLIB_VERSION_NUMBER "${OPENSSL_SHLIBVER}"|' \
		${WRKSRC}/crypto/opensslv.h
	${REINPLACE_CMD} -e 's|ERR_R_MALLOC_ERROR|ERR_R_MALLOC_FAILURE|' \
		${WRKSRC}/crypto/bio/bss_dgram.c
.if ${PORT_OPTIONS:MEXPCIPHERS}
	${REINPLACE_CMD} -e 's|TLS1_ALLOW_EXPERIMENTAL_CIPHERSUITES	0|TLS1_ALLOW_EXPERIMENTAL_CIPHERSUITES	1|' \
		${WRKSRC}/ssl/tls1.h
.endif

post-patch-MAN3-off:
	${GREP} -L openssl_manual_section ${WRKSRC}/doc/crypto/*.pod | ${XARGS} ${RM}
	${RM} -r ${WRKSRC}/doc/ssl/*.pod
	${REINPLACE_CMD} -e 's|pod doc/ssl/\*\.pod|pod|' ${WRKSRC}/Makefile.org

do-configure:
	${REINPLACE_CMD} -e "s|options 386|options|" \
		${WRKSRC}/config
	cd ${WRKSRC} \
	&& ${SETENV} CC="${CC}" FREEBSDCC="${CC}" CFLAGS="${CFLAGS}" PERL="${PERL}" \
	./config --prefix=${PREFIX} --openssldir=${OPENSSLDIR} \
		--install_prefix=${STAGEDIR} \
		-L${PREFIX}/lib ${CONFIGURE_ARGS}

post-configure:
	${REINPLACE_CMD} \
		-e 's|^MANDIR=.*$$|MANDIR=$$(PREFIX)/man|' \
		-e 's|$$(LIBDIR)/pkgconfig|libdata/pkgconfig|g' \
		-e 's|LIBVERSION=[^ ]* |LIBVERSION=${OPENSSL_SHLIBVER} |' \
		${WRKSRC}/Makefile

post-install-SHARED-on:
.for i in libcrypto libssl
	${INSTALL_DATA} ${WRKSRC}/$i.so.${OPENSSL_SHLIBVER} ${STAGEDIR}${PREFIX}/lib
	${LN} -sf $i.so.${OPENSSL_SHLIBVER} ${STAGEDIR}${PREFIX}/lib/$i.so
.endfor

post-install-DOCS-on:
	${MKDIR} ${STAGEDIR}${DOCSDIR}
	${INSTALL_DATA} ${WRKSRC}/doc/openssl.txt ${STAGEDIR}${DOCSDIR}/

test: build
	cd ${WRKSRC} && ${MAKE} test

regression-test:	test

.include <bsd.port.post.mk>
