# Created by: stb
# $FreeBSD$

PORTNAME=	netatalk
PORTVERSION=	3.1.10
PORTREVISION=	2
PORTEPOCH=	1
CATEGORIES=	net
MASTER_SITES=	SF
PKGNAMESUFFIX=	3

MAINTAINER=	marcus@FreeBSD.org
COMMENT=	File server for Mac OS X

LICENSE=	GPLv2

LIB_DEPENDS=	libgcrypt.so:security/libgcrypt \
		libevent.so:devel/libevent2

USES=		bdb:5+ gettext gmake iconv libtool perl5 pkgconfig ssl tar:bzip2
GNU_CONFIGURE=	yes
USE_LDCONFIG=	yes
USE_RC_SUBR=	netatalk
INSTALL_TARGET=install-strip

CONFIGURE_ARGS+=	--with-pkgconfdir=${PREFIX}/etc \
			--with-libgcrypt-dir=${LOCALBASE} \
			--with-uams-path=${PREFIX}/libexec/netatalk-uams \
			--with-bdb=${LOCALBASE} \
			${ICONV_CONFIGURE_BASE} \
			--localstatedir=/var \
			--disable-bundled-libevent \
			--with-libevent-header=${LOCALBASE}/include \
			--with-libevent-lib=${LOCALBASE}/lib \
			--with-ssl-dir=${OPENSSLBASE} \
			--without-dtrace

OPTIONS_DEFINE=PAM KERBEROS5 LDAP SENDFILE KERBEROS DBUS MYSQL ACL LIBWRAP
OPTIONS_DEFAULT=AVAHI DBUS KERBEROS LIBWRAP
OPTIONS_RADIO=ZEROCONF
OPTIONS_RADIO_ZEROCONF=AVAHI MDNSRESPONDER
ZEROCONF_DESC=	Zeroconf(Bonjour) support
MYSQL_DESC=	Enable MySQL CNID backend support
SENDFILE_DESC=	Enable Sendfile support
ACL_DESC=	Enable ACL support
OPTIONS_SUB=	yes
KERBEROS5_CONFIGURE_ON=	--enable-krbV-uam
KERBEROS_CONFIGURE_WITH=kerberos
KERBEROS_LIB_DEPENDS=libgpg-error.so:security/libgpg-error
PAM_CONFIGURE_WITH=pam
AVAHI_CONFIGURE_ON=	--enable-zeroconf=${LOCALBASE}
AVAHI_CFLAGS=		-I${LOCALBASE}/include -L${LOCALBASE}/lib
AVAHI_LIB_DEPENDS=		libavahi-client.so:net/avahi-app
AVAHI_SUB_LIST=		ZEROCONF="avahi_daemon"
MDNSRESPONDER_CONFIGURE_ON=	--enable-zeroconf=${LOCALBASE}
MDNSRESPONDER_CONFIGURE_ENV=	ac_cv_lib_avahi_client_avahi_client_new=no
MDNSRESPONDER_CFLAGS=		-I${LOCALBASE}/include -L${LOCALBASE}/lib
MDNSRESPONDER_LIB_DEPENDS=		libdns_sd.so:net/mDNSResponder
MDNSRESPONDER_SUB_LIST=	ZEROCONF="mdnsd"
LDAP_CONFIGURE_ON=	--with-ldap=${LOCALBASE}
LDAP_CFLAGS=		-I${LOCALBASE}/include -L${LOCALBASE}/lib
LDAP_USE=	OPENLDAP=yes
LDAP_CONFIGURE_OFF=	--without-ldap
SENDFILE_CONFIGURE_ENABLE=sendfile
DBUS_USES=	python:2
DBUS_USE=	GNOME=glib20
DBUS_LIB_DEPENDS=	libdbus-glib-1.so:devel/dbus-glib \
			libdbus-1.so:devel/dbus
DBUS_RUN_DEPENDS=	${PYTHON_SITELIBDIR}/dbus/_dbus.py:devel/py-dbus
MYSQL_USE=	MYSQL=yes
MYSQL_CONFIGURE_OFF=--with-mysql-config=/nonexistent
ACL_LIB_DEPENDS=	libsunacl.so:sysutils/libsunacl
ACL_CONFIGURE_WITH=acls
LIBWRAP_CONFIGURE_ENABLE=tcp-wrappers

CONFLICTS=	bigloo-2.* cap-6.0.* tct-1.* netatalk-[12]* yudit-[0-9]*

.include <bsd.port.pre.mk>

.if ${PORT_OPTIONS:MAVAHI}=="" && ${PORT_OPTIONS:MMDNSRESPONDER}==""
SUB_LIST+=	ZEROCONF=""
CONFIGURE_ARGS+=--disable-zeroconf
.endif

post-patch:
	@${REINPLACE_CMD} -e 's|%%DB_NAME%%|${BDB_INCLUDE_DIR:T}| ; \
		s|%%DB_LIB%%|-l${BDB_LIB_NAME}|g ; \
		s|%%LOCALBASE%%|${LOCALBASE}|g' \
		${WRKSRC}/configure
	@${REINPLACE_CMD} -e 's|\.dist|\.sample|g' \
	    	${WRKSRC}/config/Makefile.in
	@${REINPLACE_CMD} -e 's|%%PYTHONCMD%%|${PYTHONCMD}|' \
	    	${WRKSRC}/contrib/shell_utils/afpstats

post-install:
	${INSTALL_SCRIPT} ${WRKSRC}/contrib/macusers/macusers \
		${STAGEDIR}${PREFIX}/bin/macusers

.if ${PORT_OPTIONS:MPAM}
	${INSTALL_DATA} ${FILESDIR}/pam.conf ${STAGEDIR}${PREFIX}/etc/pam.d/netatalk.sample
.endif

.include <bsd.port.post.mk>
