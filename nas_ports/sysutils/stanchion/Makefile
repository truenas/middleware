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
        USERS=${USERS} \
        GROUPS=${GROUPS}


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
	${INSTALL_DATA} ${WRKSRC}/rel/stanchion/etc/stanchion.conf ${STAGEDIR}${STANCHION_CONFDIR}/stanchion.conf
	${INSTALL_DATA} ${WRKSRC}/rel/stanchion/etc/advanced.config ${STAGEDIR}${STANCHION_CONFDIR}/advanced.config
	${INSTALL_DATA} ${WRKSRC}/rel/stanchion/etc/cert.pem ${STAGEDIR}${STANCHION_CONFDIR}/cert.pem
	${INSTALL_DATA} ${WRKSRC}/rel/stanchion/etc/key.pem ${STAGEDIR}${STANCHION_CONFDIR}/key.pem
	(cd ${WRKSRC}/rel/stanchion/lib/ && ${COPYTREE_BIN} . ${STAGEDIR}${STANCHION_LIBDIR})
	(cd ${WRKSRC}/rel/stanchion/bin/ && ${COPYTREE_BIN} . ${STAGEDIR}${PREFIX}/sbin/)
	(cd ${WRKSRC}/rel/stanchion/releases && ${COPYTREE_SHARE} . ${STAGEDIR}${STANCHION_HOMEDIR}/releases)
	${CP} -R ${WRKSRC}/rel/stanchion/erts-* ${STAGEDIR}${STANCHION_HOMEDIR}

.include <bsd.port.post.mk>
