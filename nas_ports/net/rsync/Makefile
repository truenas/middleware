# Created by: David O'Brien (obrien@cs.ucdavis.edu)
# $FreeBSD$

PORTNAME=	rsync
PORTVERSION=	3.1.2
CATEGORIES=	net ipv6
PORTREVISION=	2
MASTER_SITES=	http://rsync.samba.org/ftp/rsync/ \
		ftp://ftp.samba.org/pub/rsync/ \
		ftp://ftp.sunet.se/pub/unix/admin/rsync/  \
		ftp://ftp.fu-berlin.de/pub/unix/network/rsync/ \
		http://www.mirrorservice.org/sites/rsync.samba.org/ \
		LOCAL/ehaupt/rsync
DISTFILES=	${DISTNAME}${EXTRACT_SUFX}

MAINTAINER=	ehaupt@FreeBSD.org
COMMENT=	Network file distribution/synchronization utility

LICENSE=	GPLv3

USES=		cpe

CPE_VENDOR=	samba
CPE_PRODUCT=	rsync

PATCH_STRIP=	-p1
GNU_CONFIGURE=	yes
USE_RC_SUBR=	rsyncd
SUB_LIST=	NAME=rsyncd

INSTALL_TARGET=	install-strip

CONFIGURE_ARGS=	--disable-debug --enable-ipv6 \
		--with-rsyncd-conf=${ETCDIR}/rsyncd.conf

PORTDOCS=	NEWS README csprotocol.txt tech_report.tex

# define options
OPTIONS_DEFINE=		DOCS POPT_PORT ZLIB_BASE SSH ICONV
OPTIONS_RADIO=		PTS
OPTIONS_RADIO_PTS=	TIMELIMIT RENAMED FLAGS ATIMES ACL

# options provided upstream
POPT_PORT_DESC=	Use popt from devel/popt instead of bundled one
ZLIB_BASE_DESC=	Use zlib from base instead of bundled one
SSH_DESC=	Use SSH instead of RSH

# options provided by patch (mutually exclusive)
PTS_DESC=	Functionality provided by third party patches
TIMELIMIT_DESC=	Time limit patch
RENAMED_DESC=	Add support for renamed file detection
FLAGS_DESC=	File system flags support patch, adds --fileflags
ATIMES_DESC=	Preserve access times, adds --atimes (BROKEN)
ACL_DESC=	Add backward-compatibility for the --acls option

# define default options
OPTIONS_DEFAULT=SSH FLAGS

ZLIB_BASE_CONFIGURE_ON=	--with-included-zlib=no
TIMELIMIT_EXTRA_PATCHES=	${WRKSRC}/patches/time-limit.diff
ATIMES_EXTRA_PATCHES=		${WRKSRC}/patches/atimes.diff
FLAGS_EXTRA_PATCHES=		${WRKSRC}/patches/fileflags.diff \
				${FILESDIR}/extrapatch-main.c
RENAMED_EXTRA_PATCHES=		${WRKSRC}/patches/detect-renamed.diff
ACL_EXTRA_PATCHES=		${WRKSRC}/patches/acls.diff \
				${FILESDIR}/extrapatch-acl

ICONV_USES=	iconv
ICONV_CPPFLAGS=	-I${LOCALBASE}/include
ICONV_LDFLAGS=	-L${LOCALBASE}/lib
ICONV_CONFIGURE_ENABLE=	iconv iconv-open

POPT_PORT_LIB_DEPENDS=	libpopt.so:${PORTSDIR}/devel/popt
POPT_PORT_CPPFLAGS=	-I${LOCALBASE}/include
POPT_PORT_LDFLAGS=	-L${LOCALBASE}/lib
POPT_CONFIGURE_WITH=	included-popt

SSH_CONFIGURE_ON=	--with-rsh=ssh
SSH_CONFIGURE_OFF=	--with-rsh=rsh

.include <bsd.port.options.mk>

.if ${PORT_OPTIONS:MICONV} || ${PORT_OPTIONS:MFLAGS} || ${PORT_OPTIONS:MACL} || make(makesum) || ${PORT_OPTIONS:MTIMELIMIT} || ${PORT_OPTIONS:MATIMES} || ${PORT_OPTIONS:MRENAMED}
DISTFILES+=	${PORTNAME}-patches-${PORTVERSION}${EXTRACT_SUFX}
.endif

.include <bsd.port.pre.mk>

.if empty(ICONV_LIB)
CONFIGURE_ARGS+=ac_cv_search_libiconv_open=no
.endif

post-patch:
	@${REINPLACE_CMD} -e 's|perl.*|${DO_NADA}|' ${WRKSRC}/Makefile.in
	@${REINPLACE_CMD} -e 's:/etc/:${ETCDIR}/:g'  \
		${WRKSRC}/rsync.h ${WRKSRC}/rsync.1 ${WRKSRC}/rsyncd.conf.5

post-install:
	@${MKDIR} ${STAGEDIR}${ETCDIR}
	${INSTALL_DATA} ${FILESDIR}/rsyncd.conf.sample ${STAGEDIR}${ETCDIR}/
	@${MKDIR} ${STAGEDIR}${DOCSDIR}
	${INSTALL_DATA} ${PORTDOCS:S,^,${WRKSRC}/,} ${STAGEDIR}${DOCSDIR}

test: build
	@(cd ${WRKSRC} && ${MAKE_CMD} check)

.include <bsd.port.post.mk>
