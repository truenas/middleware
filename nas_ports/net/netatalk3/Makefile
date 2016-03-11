# Created by: stb
# $FreeBSD$

PORTNAME=	netatalk
PORTVERSION=	3.1.8
PORTEPOCH=	1
CATEGORIES=	net
MASTER_SITES=	SF
PKGNAMESUFFIX=	3

MAINTAINER=	marcus@FreeBSD.org
COMMENT=	File server for Mac OS X

LICENSE=	GPLv2

LIB_DEPENDS=	libgcrypt.so:${PORTSDIR}/security/libgcrypt \
    		libevent.so:${PORTSDIR}/devel/libevent2

USE_BDB=	5+
USES=		iconv gmake pkgconfig perl5 libtool tar:bzip2
GNU_CONFIGURE=	yes
USE_LDCONFIG=	yes
USE_RC_SUBR=	netatalk

CONFIGURE_ARGS+=	--with-pkgconfdir=${PREFIX}/etc \
			--with-libgcrypt-dir=${LOCALBASE} \
			--with-uams-path=${PREFIX}/libexec/netatalk-uams \
			--with-bdb=${LOCALBASE} \
			${ICONV_CONFIGURE_BASE} \
			--localstatedir=/var \
			--disable-bundled-libevent \
			--with-libevent-header=${LOCALBASE}/include \
			--with-libevent-lib=${LOCALBASE}/lib

OPTIONS_DEFINE=PAM KRB5 LDAP SENDFILE KERBEROS DBUS MYSQL ACL TCPWRAP
OPTIONS_DEFAULT=KERBEROS DBUS TCPWRAP
OPTIONS_RADIO=ZEROCONF
OPTIONS_RADIO_ZEROCONF=AVAHI MDNSRESPONDER
OPTIONS_DEFAULT+=AVAHI

NOZEROCONF_DESC=Disable Zeroconf(Bonjour) support
KRB5_DESC=	Enable Kerberos V UAM
#DTRACE_DESC=	Enable DTrace support
MYSQL_DESC=	Enable MySQL CNID backend support
SENDFILE_DESC=	Enable Sendfile support
ACL_DESC=	Enable ACL support
TCPWRAP_DESC=	Enable TCP Wrappers support

.include <bsd.port.options.mk>

CONFLICTS=	bigloo-2.* cap-6.0.* tct-1.* netatalk-[12]* yudit-[0-9]*

.if ${PORT_OPTIONS:MKRB5}
CONFIGURE_ARGS+=	--enable-krbV-uam
PLIST_SUB+=		NETATALKKRB5=""
.else
PLIST_SUB+=		NETATALKKRB5="@comment "
.endif

.if ${PORT_OPTIONS:MDTRACE}
CONFIGURE_ARGS+=	--with-dtrace
.else
CONFIGURE_ARGS+=	--without-dtrace
.endif

.if ${PORT_OPTIONS:MKERBEROS}
CONFIGURE_ARGS+=	--with-kerberos
.else
CONFIGURE_ARGS+=	--without-kerberos
.endif

.if ${PORT_OPTIONS:MPAM}
CONFIGURE_ARGS+=	--with-pam
PLIST_SUB+=		NETATALKPAM=""
.else
CONFIGURE_ARGS+=	--without-pam
PLIST_SUB+=		NETATALKPAM="@comment "
.endif

.if ${PORT_OPTIONS:MNOZEROCONF}
CONFIGURE_ARGS+=	--disable-zeroconf
SUB_LIST+=		ZEROCONF=""
.endif

.if ${PORT_OPTIONS:MAVAHI}
CONFIGURE_ARGS+=	--enable-zeroconf=${LOCALBASE}
CFLAGS+=		-I${LOCALBASE}/include -L${LOCALBASE}/lib
LIB_DEPENDS+=		libavahi-client.so:${PORTSDIR}/net/avahi-app
SUB_LIST+=		ZEROCONF="avahi_daemon"
.endif

.if ${PORT_OPTIONS:MMDNSRESPONDER}
CONFIGURE_ARGS+=	--enable-zeroconf=${LOCALBASE}
CFLAGS+=		-I${LOCALBASE}/include -L${LOCALBASE}/lib
LIB_DEPENDS+=		libdns_sd.so:${PORTSDIR}/net/mDNSResponder
SUB_LIST+=		ZEROCONF="mdnsd"
.endif

.if ${PORT_OPTIONS:MLDAP}
CONFIGURE_ARGS+=	--with-ldap=${LOCALBASE}
CFLAGS+=		-I${LOCALBASE}/include -L${LOCALBASE}/lib
USE_OPENLDAP=		yes
.else
CONFIGURE_ARGS+=	--without-ldap
.endif

.if ${PORT_OPTIONS:MSENDFILE}
CONFIGURE_ARGS+=	--enable-sendfile
.else
CONFIGURE_ARGS+=	--disable-sendfile
.endif

.if ${PORT_OPTIONS:MDBUS} || exists(${LOCALBASE}/libdata/pkgconfig/dbus-glib-1.pc)
USES+=			python:2
LIB_DEPENDS+=		libdbus-glib-1.so:${PORTSDIR}/devel/dbus-glib
RUN_DEPENDS+=		${PYTHON_SITELIBDIR}/dbus/_dbus.py:${PORTSDIR}/devel/py-dbus
PLIST_SUB+=		DBUS=""
.else
PLIST_SUB+=		DBUS="@comment "
.endif

.if ${PORT_OPTIONS:MMYSQL}
USE_MYSQL=	yes
.else
CONFIGURE_ARGS+=--with-mysql-config=/nonexistent
.endif

.if ${PORT_OPTIONS:MACL}
LIB_DEPENDS+=	libsunacl.so:${PORTSDIR}/sysutils/libsunacl
CONFIGURE_ARGS+=--with-acls
.else
CONFIGURE_ARGS+=--without-acls
.endif

.if ${PORT_OPTIONS:MTCPWRAP}
CONFIGURE_ARGS+=--enable-tcp-wrappers
.else
CONFIGURE_ARGS+=--disable-tcp-wrappers
.endif

post-patch:
	@${REINPLACE_CMD} -e 's|%%DB_NAME%%|${BDB_INCLUDE_DIR:T}| ; \
	    	s|%%DB_LIB%%|-l${BDB_LIB_NAME}|g ; \
		s|%%LOCALBASE%%|${LOCALBASE}|g' \
		${WRKSRC}/configure

post-stage:
	@${RM} -f ${STAGEDIR}${PREFIX}/etc/afp.conf \
		${STAGEDIR}${PREFIX}/etc/extmap.conf

post-install:
	${INSTALL_SCRIPT} ${WRKSRC}/contrib/macusers/macusers \
		${STAGEDIR}${PREFIX}/bin/macusers
	[ -f ${STAGEDIR}${PREFIX}/etc/afp.conf ] || \
		${INSTALL_DATA} -c ${STAGEDIR}${PREFIX}/etc/afp.conf.dist ${STAGEDIR}${PREFIX}/etc/afp.conf
	[ -f ${STAGEDIR}${PREFIX}/etc/extmap.conf ] || \
		${INSTALL_DATA} -c ${STAGEDIR}${PREFIX}/etc/extmap.conf.dist ${STAGEDIR}${PREFIX}/etc/extmap.conf

.include <bsd.port.mk>
