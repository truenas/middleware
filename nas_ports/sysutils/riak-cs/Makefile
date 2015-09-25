# $FreeBSD$

PORTNAME=	riak-cs
PORTVERSION=	2.0.1
CATEGORIES=	sysutils
MASTER_SITES=	http://s3.amazonaws.com/downloads.basho.com/riak-cs/${PORTVERSION:R}/${PORTVERSION}/ \
	http://downloads.basho.com.s3.amazonaws.com/riak-cs/${PORTVERSION:R}/${PORTVERSION}/
DISTNAME=	riak-cs-${PORTVERSION}
DISTFILES=	${DISTNAME}${EXTRACT_SUFX}
EXTRACT_ONLY=	${DISTNAME}${EXTRACT_SUFX}

MAINTAINER=	scott@ixsystems.com
COMMENT=	Riak CS is an open source, distributed, S3 interface to RIAK KV

LICENSE=	APACHE20

BUILD_DEPENDS=	${LOCALBASE}/lib/riak-erlang/bin/erlc:${PORTSDIR}/lang/erlang-riak

USES=		gmake readline
USE_RC_SUBR=	riak-cs
USE_GCC=	yes

USERS=		riakcs
GROUPS=		riak

RIAKCS_CONFDIR?=	${PREFIX}/etc/riak-cs
RIAKCS_DBDIR?=	/var/db/riak-cs
RIAKCS_HOMEDIR?=	${PREFIX}/lib/riak-cs
RIAKCS_LIBDIR?=	${PREFIX}/lib/riak-cs/lib
RIAKCS_LOGDIR?=	/var/log/riak-cs

PLIST=		${WRKDIR}/pkg-plist
PLIST_SUB+=	RIAKCS_CONFDIR=${RIAKCS_CONFDIR} \
	RIAKCS_DBDIR=${RIAKCS_DBDIR} \
	RIAKCS_HOMEDIR=${RIAKCS_HOMEDIR} \
	RIAKCS_LIBDIR=${RIAKCS_LIBDIR} \
	RIAKCS_LOGDIR=${RIAKCS_LOGDIR} \
 	USERS=${USERS} \
        GROUPS=${GROUPS}


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
.for d in ${RIAKCS_CONFDIR} ${RIAKCS_LOGDIR} ${RIAKCS_DBDIR} ${RIAKCS_LIBDIR} ${RIAKCS_HOMEDIR}
	${MKDIR} ${STAGEDIR}${d}
.endfor
	${INSTALL_DATA} ${WRKSRC}/rel/riak-cs/etc/riak-cs.conf ${STAGEDIR}${RIAKCS_CONFDIR}/riak-cs.conf
	${INSTALL_DATA} ${WRKSRC}/rel/riak-cs/etc/advanced.config ${STAGEDIR}${RIAKCS_CONFDIR}/advanced.config
	${INSTALL_DATA} ${WRKSRC}/rel/riak-cs/etc/cert.pem ${STAGEDIR}${RIAKCS_CONFDIR}/cert.pem
	${INSTALL_DATA} ${WRKSRC}/rel/riak-cs/etc/key.pem ${STAGEDIR}${RIAKCS_CONFDIR}/key.pem
	(cd ${WRKSRC}/rel/riak-cs/lib/ && ${COPYTREE_BIN} . ${STAGEDIR}${RIAKCS_LIBDIR})
	(cd ${WRKSRC}/rel/riak-cs/bin/ && ${COPYTREE_BIN} . ${STAGEDIR}${PREFIX}/sbin/)
	(cd ${WRKSRC}/rel/riak-cs/lib/basho-patches && ${COPYTREE_SHARE} . ${STAGEDIR}${RIAKCS_LIBDIR}/basho-patches)
	(cd ${WRKSRC}/rel/riak-cs/releases && ${COPYTREE_SHARE} . ${STAGEDIR}${RIAKCS_HOMEDIR}/releases)
	${CP} -R ${WRKSRC}/rel/riak-cs/erts-* ${STAGEDIR}${RIAKCS_HOMEDIR}

.include <bsd.port.post.mk>
