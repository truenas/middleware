# $FreeBSD$

PORTNAME=	stanchion
PORTVERSION=	2.0.0
CATEGORIES=	databases
MASTER_SITES=	http://s3.amazonaws.com/downloads.basho.com/stanchion/${PORTVERSION:R}/${PORTVERSION}/ \
	http://downloads.basho.com.s3.amazonaws.com/stanchion/${PORTVERSION:R}/${PORTVERSION}/
DISTNAME=	stanchion-${PORTVERSION}
DISTFILES=	${DISTNAME}${EXTRACT_SUFX}
EXTRACT_ONLY=	${DISTNAME}${EXTRACT_SUFX}

MAINTAINER=	scott@ixsystems.com
COMMENT=	Stanchion is an open source, database cluster control for RIAK

LICENSE=	APACHE20

BUILD_DEPENDS=	${LOCALBASE}/lib/riak-erlang/bin/erlc:${PORTSDIR}/lang/riak-erlang

USES=		gmake readline
USE_RC_SUBR=	stanchion
USE_GCC=	yes

USERS=		stanchion
GROUPS=		riak

STANCHION_CONFDIR?=	${PREFIX}/etc/stanchion
STANCHION_DBDIR?=	/var/db/stanchion
STANCHION_HOMEDIR?=	${PREFIX}/lib/stanchion
STANCHION_LIBDIR?=	${PREFIX}/lib/stanchion/lib
STANCHION_LOGDIR?=	/var/log/stanchion

PLIST=		${WRKDIR}/pkg-plist
PLIST_SUB+=	STANCHION_CONFDIR=${STANCHION_CONFDIR} \
	STANCHION_DBDIR=${STANCHION_DBDIR} \
	STANCHION_HOMEDIR=${STANCHION_HOMEDIR} \
	STANCHION_LIBDIR=${STANCHION_LIBDIR} \
	STANCHION_LOGDIR=${STANCHION_LOGDIR} \

ALL_TARGET=	rel
MAKE_JOBS_UNSAFE=yes
MAKE_ENV=	PATH=${LOCALBASE}/lib/riak-erlang/bin:${PATH}

.include <bsd.port.pre.mk>

pre-install:
	${RM} -f ${PLIST}
	${CAT} ${PKGDIR}/pkg-plist >> ${PLIST}
	(cd ${WRKSRC}/rel/stanchion; ${FIND} releases -type f \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn | ${SED} -e 's/^/lib\//' \
		| ${AWK} '{print "lib/stanchion/"$$2 }' >> ${PLIST})
	(cd ${WRKSRC}/rel/stanchion; ${FIND} erts-* -type f \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn  \
		| ${AWK} '{print "lib/stanchion/"$$2 }' >> ${PLIST})
	(cd ${WRKSRC}/rel; ${FIND} stanchion/lib -type f \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn | ${SED} -e 's/^/lib\//' \
		| ${AWK} '{print "lib/"$$2 }' >> ${PLIST})
	(cd ${WRKSRC}/rel; ${FIND} stanchion/lib -type d -empty \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn | ${SED} -e 's/^/lib\//' \
		| ${AWK} '{print "@dir lib/"$$2 }' >> ${PLIST})

do-install:
.for d in ${STANCHION_CONFDIR} ${STANCHION_LOGDIR} ${STANCHION_DBDIR} ${STANCHION_LIBDIR} ${STANCHION_HOMEDIR}
	${MKDIR} ${STAGEDIR}${d}
.endfor
	${INSTALL_DATA} ${WRKSRC}/rel/stanchion/etc/stanchion.conf ${STAGEDIR}${STANCHION_CONFDIR}/stanchion.conf.sample
	${INSTALL_DATA} ${WRKSRC}/rel/stanchion/etc/solr-log4j.properties ${STAGEDIR}${STANCHION_CONFDIR}/solr-log4j.properties.sample
	(cd ${WRKSRC}/rel/stanchion/lib/ && ${COPYTREE_BIN} . ${STAGEDIR}${STANCHION_LIBDIR})
	(cd ${WRKSRC}/rel/stanchion/bin/ && ${COPYTREE_BIN} . ${STAGEDIR}${PREFIX}/sbin/)
	(cd ${WRKSRC}/rel/stanchion/lib/basho-patches && ${COPYTREE_SHARE} . ${STAGEDIR}${STANCHION_LIBDIR}/basho-patches)
	(cd ${WRKSRC}/rel/stanchion/releases && ${COPYTREE_SHARE} . ${STAGEDIR}${STANCHION_HOMEDIR}/releases)
	${CP} -R ${WRKSRC}/rel/stanchion/erts-* ${STAGEDIR}${STANCHION_HOMEDIR}
	${INSTALL_MAN} ${WRKSRC}/doc/man/man1/stanchion.1.gz ${STAGEDIR}${MANPREFIX}/man/man1/
	${INSTALL_MAN} ${WRKSRC}/doc/man/man1/stanchion-admin.1.gz ${STAGEDIR}${MANPREFIX}/man/man1/
	${INSTALL_MAN} ${WRKSRC}/doc/man/man1/stanchion-debug.1.gz ${STAGEDIR}${MANPREFIX}/man/man1/
	${INSTALL_MAN} ${WRKSRC}/doc/man/man1/search-cmd.1.gz ${STAGEDIR}${MANPREFIX}/man/man1/
	@${STRIP_CMD} ${STAGEDIR}${PREFIX}/lib/stanchion/lib/bitcask-1.7.0/priv/bitcask.so
	@${STRIP_CMD} ${STAGEDIR}${PREFIX}/lib/stanchion/lib/erlang_js-1.3.0-0-g07467d8/priv/erlang_js_drv.so
	@${STRIP_CMD} ${STAGEDIR}${PREFIX}/lib/stanchion/lib/syslog-1.0.2/priv/syslog_drv.so
	@${STRIP_CMD} ${STAGEDIR}${PREFIX}/lib/stanchion/lib/canola-2.0.0-0-g9bdfee8/priv/canola-port
	@${STRIP_CMD} ${STAGEDIR}${PREFIX}/lib/stanchion/lib/sext-1.1p3-0-g846b9cc/priv/sext.so

.include <bsd.port.post.mk>
