# $FreeBSD$

PORTNAME=	riak-cs
PORTVERSION=	2.0.1
CATEGORIES=	databases
MASTER_SITES=	http://s3.amazonaws.com/downloads.basho.com/riak-cs/${PORTVERSION:R}/${PORTVERSION}/ \
	http://downloads.basho.com.s3.amazonaws.com/riak-cs/${PORTVERSION:R}/${PORTVERSION}/
DISTNAME=	riak-cs-${PORTVERSION}
DISTFILES=	${DISTNAME}${EXTRACT_SUFX}
EXTRACT_ONLY=	${DISTNAME}${EXTRACT_SUFX}

MAINTAINER=	scott@ixsystems.com
COMMENT=	Riak CS is an open source, distributed, S3 interface to RIAK KV

LICENSE=	APACHE20

BUILD_DEPENDS=	${LOCALBASE}/lib/riak-erlang/bin/erlc:${PORTSDIR}/lang/riak-erlang

USES=		gmake readline
USE_RC_SUBR=	riak-cs
USE_GCC=	yes

USERS=		riakcs
GROUPS=		riak

RIAK_CONFDIR?=	${PREFIX}/etc/riak-cs
RIAK_DBDIR?=	/var/db/riak-cs
RIAK_HOMEDIR?=	${PREFIX}/lib/riak-cs
RIAK_LIBDIR?=	${PREFIX}/lib/riak-cs/lib
RIAK_LOGDIR?=	/var/log/riak-cs

PLIST=		${WRKDIR}/pkg-plist
PLIST_SUB+=	RIAK_CONFDIR=${RIAK_CONFDIR} \
	RIAK_DBDIR=${RIAK_DBDIR} \
	RIAK_HOMEDIR=${RIAK_HOMEDIR} \
	RIAK_LIBDIR=${RIAK_LIBDIR} \
	RIAK_LOGDIR=${RIAK_LOGDIR} \

ALL_TARGET=	rel
MAKE_JOBS_UNSAFE=yes
MAKE_ENV=	PATH=${LOCALBASE}/lib/riak-erlang/bin:${PATH}

.include <bsd.port.pre.mk>

post-patch:
	@${REINPLACE_CMD} 's|%%PREFIX%%|${PREFIX}|g' ${WRKSRC}/rel/vars.config

pre-install:
	${RM} -f ${PLIST}
	${CAT} ${PKGDIR}/pkg-plist >> ${PLIST}
	(cd ${WRKSRC}/rel/riak-cs; ${FIND} releases -type f \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn | ${SED} -e 's/^/lib\//' \
		| ${AWK} '{print "lib/riak-cs/"$$2 }' >> ${PLIST})
	(cd ${WRKSRC}/rel/riak-cs; ${FIND} erts-* -type f \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn  \
		| ${AWK} '{print "lib/riak-cs/"$$2 }' >> ${PLIST})
	(cd ${WRKSRC}/rel; ${FIND} riak-cs/lib -type f \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn | ${SED} -e 's/^/lib\//' \
		| ${AWK} '{print "lib/"$$2 }' >> ${PLIST})
	(cd ${WRKSRC}/rel; ${FIND} riak-cs/lib -type d -empty \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn | ${SED} -e 's/^/lib\//' \
		| ${AWK} '{print "@dir lib/"$$2 }' >> ${PLIST})

do-install:
.for d in ${RIAK_CONFDIR} ${RIAK_LOGDIR} ${RIAK_DBDIR} ${RIAK_LIBDIR} ${RIAK_HOMEDIR}
	${MKDIR} ${STAGEDIR}${d}
.endfor
	${INSTALL_DATA} ${WRKSRC}/rel/riak-cs/etc/riak-cs.conf ${STAGEDIR}${RIAK_CONFDIR}/riak-cs.conf.sample
	(cd ${WRKSRC}/rel/riak-cs/lib/ && ${COPYTREE_BIN} . ${STAGEDIR}${RIAK_LIBDIR})
	(cd ${WRKSRC}/rel/riak-cs/bin/ && ${COPYTREE_BIN} . ${STAGEDIR}${PREFIX}/sbin/)
	(cd ${WRKSRC}/rel/riak-cs/lib/basho-patches && ${COPYTREE_SHARE} . ${STAGEDIR}${RIAK_LIBDIR}/basho-patches)
	(cd ${WRKSRC}/rel/riak-cs/releases && ${COPYTREE_SHARE} . ${STAGEDIR}${RIAK_HOMEDIR}/releases)
	${CP} -R ${WRKSRC}/rel/riak-cs/erts-* ${STAGEDIR}${RIAK_HOMEDIR}
	${INSTALL_MAN} ${WRKSRC}/doc/man/man1/riak-cs.1.gz ${STAGEDIR}${MANPREFIX}/man/man1/
	${INSTALL_MAN} ${WRKSRC}/doc/man/man1/riak-cs-admin.1.gz ${STAGEDIR}${MANPREFIX}/man/man1/
	${INSTALL_MAN} ${WRKSRC}/doc/man/man1/riak-cs-debug.1.gz ${STAGEDIR}${MANPREFIX}/man/man1/
	${INSTALL_MAN} ${WRKSRC}/doc/man/man1/search-cmd.1.gz ${STAGEDIR}${MANPREFIX}/man/man1/
	@${STRIP_CMD} ${STAGEDIR}${PREFIX}/lib/riak-cs/lib/bitcask-1.7.0/priv/bitcask.so
	@${STRIP_CMD} ${STAGEDIR}${PREFIX}/lib/riak-cs/lib/erlang_js-1.3.0-0-g07467d8/priv/erlang_js_drv.so
	@${STRIP_CMD} ${STAGEDIR}${PREFIX}/lib/riak-cs/lib/syslog-1.0.2/priv/syslog_drv.so
	@${STRIP_CMD} ${STAGEDIR}${PREFIX}/lib/riak-cs/lib/canola-2.0.0-0-g9bdfee8/priv/canola-port
	@${STRIP_CMD} ${STAGEDIR}${PREFIX}/lib/riak-cs/lib/sext-1.1p3-0-g846b9cc/priv/sext.so

.include <bsd.port.post.mk>
