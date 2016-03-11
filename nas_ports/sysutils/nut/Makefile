# Created by: Boris Popov <bp@FreeBSD.org>
# $FreeBSD$

PORTNAME=	nut
PORTVERSION=	2.7.3
PORTREVISION=	4
CATEGORIES=	sysutils
MASTER_SITES=	http://www.networkupstools.org/source/${PORTVERSION:R}/
DISTFILES=	${DISTNAME}${EXTRACT_SUFX} ${DISTNAME}${EXTRACT_SUFX}.sig
EXTRACT_ONLY=	${DISTNAME}${EXTRACT_SUFX}

MAINTAINER=	cy@FreeBSD.org
COMMENT=	Network UPS Tools

USE_AUTOTOOLS=	autoconf
GNU_CONFIGURE=	yes
USE_LDCONFIG=	yes
USES=		gmake pkgconfig libtool

NUT_USER?=	uucp
NUT_GROUP?=	uucp
STATEDIR?=	/var/db/nut
PLIST_SUB+=	NUT_USER=${NUT_USER}
PLIST_SUB+=	NUT_GROUP=${NUT_GROUP}

OPTIONS_DEFAULT=SERIAL USB SNMP NEON IPMI_OFF
OPTIONS_DEFINE=	SERIAL USB SNMP NEON PDU CGI BASH AVAHI OPENSSL DOCS
OPTIONS_SINGLE=	IPMI
OPTIONS_SINGLE_IPMI=	IPMI_OFF IPMIPSU FREEIPMI

SERIAL_DESC=	SERIAL support
USB_DESC=	USB support
SNMP_DESC=	SNMP support
NEON_DESC=	NEON XML/HTTP support
PDU_DESC=	Powerman PDU support
CGI_DESC=	Web CGI interface
BASH_DESC=	Bash Completion support
AVAHI_DESC=	Avahi support
IPMI_OFF_DESC=	No IPMI support
FREEIPMI_DESC=	freeipmi support
IPMIPSU_DESC=	Use nut-ipmipsu support (experimental)

USE_RC_SUBR=	nut nut_upsmon nut_upslog
SUB_LIST+=	STATEDIR=${STATEDIR}
PLIST_SUB+=	STATEDIR=${STATEDIR}

PORTDOCS=	*

.include <bsd.port.options.mk>

CONFIGURE_ARGS=	--sysconfdir=${PREFIX}/etc/nut \
		--program-transform-name="" \
		--localstatedir=${STATEDIR} \
		--datadir=${PREFIX}/etc/nut \
		--with-devd-dir=${PREFIX}/etc/devd \
		--with-drvpath=${PREFIX}/libexec/nut \
		--with-statepath=${STATEDIR} \
		--with-altpidpath=${STATEDIR} \
		--with-pidpath=${STATEDIR} \
		--with-pkgconfig-dir=${PREFIX}/libdata/pkgconfig \
		--with-user=${NUT_USER} \
		--with-group=${NUT_GROUP} \
		--with-dev

.if ${PORT_OPTIONS:MCGI}
LIB_DEPENDS+=	libgd.so:${PORTSDIR}/graphics/gd
CGIDIR?=	${PREFIX}/www/cgi-bin/${PORTNAME}
CGIDIR_REL?=	${CGIDIR:S,^${PREFIX}/,,}
CONFIGURE_ARGS+=	--with-cgi --with-cgipath=${CGIDIR} \
			--with-htmlpath=${WWWDIR} \
			--with-gd-includes=-I${LOCALBASE}/include \
			--with-gd-libs="-L${LOCALBASE}/lib -lgd"
PLIST_SUB+=	NUT_CGI=""
PLIST_SUB+=	CGIDIR="${CGIDIR_REL}"
PLIST_SUB+=	CGIETCDIR="etc/nut/"
.else
CONFIGURE_ARGS+=	--without-cgi
PLIST_SUB+=	NUT_CGI="@comment "
.endif

.if ${PORT_OPTIONS:MSERIAL}
CONFIGURE_ARGS+=	--with-serial
PLIST_SUB+=	NUT_SERIAL=""
.else
CONFIGURE_ARGS+=	--without-serial
PLIST_SUB+=	NUT_SERIAL="@comment "
.endif

.if ${PORT_OPTIONS:MUSB}
#EXTRA_PATCHES=	${FILESDIR}/extra-patch-m4_nut_check_libusb.m4
CONFIGURE_ARGS+=	--with-usb=auto
PLIST_SUB+=	NUT_USB=""
.else
CONFIGURE_ARGS+=	--without-usb
PLIST_SUB+=	NUT_USB="@comment "
.endif

.if ${PORT_OPTIONS:MSNMP}
LIB_DEPENDS+=	libnetsnmp.so:${PORTSDIR}/net-mgmt/net-snmp
CONFIGURE_ARGS+=	--with-snmp
PLIST_SUB+=	NUT_SNMP=""
.else
CONFIGURE_ARGS+=	--without-snmp
PLIST_SUB+=	NUT_SNMP="@comment "
.endif

.if ${PORT_OPTIONS:MNEON}
LIB_DEPENDS+=	libneon.so:${PORTSDIR}/www/neon
CONFIGURE_ARGS+=	--with-neonxml
PLIST_SUB+=	NUT_NEON=""
.else
CONFIGURE_ARGS+=	--without-neonxml
CONFIGURE_ARGS+=	--disable-neonxml
PLIST_SUB+=	NUT_NEON="@comment "
.endif

.if ${PORT_OPTIONS:MPDU}
LIB_DEPENDS+=	libpowerman.so:${PORTSDIR}/sysutils/powerman
CONFIGURE_ARGS+=	--with-powerman
PLIST_SUB+=	NUT_PDU=""
.else
CONFIGURE_ARGS+=	--without-powerman
PLIST_SUB+=	NUT_PDU="@comment "
.endif

.if ${PORT_OPTIONS:MBASH}
BUILD_DEPENDS+=	${LOCALBASE}/share/bash-completion/bash_completion.sh:${PORTSDIR}/shells/bash-completion
RUN_DEPENDS+=	${LOCALBASE}/share/bash-completion/bash_completion.sh:${PORTSDIR}/shells/bash-completion
PLIST_SUB+=	BASH=""
.else
PLIST_SUB+=	BASH="@comment "
.endif

.if ${PORT_OPTIONS:MAVAHI}
BUILD_DEPENDS+=	${LOCALBASE}/include/avahi-ui/avahi-ui.h:${PORTSDIR}/net/avahi-header
BUILD_DEPENDS+=	avahi-daemon:${PORTSDIR}/net/avahi-app
RUN_DEPENDS+=	avahi-daemon:${PORTSDIR}/net/avahi-app
CONFIGURE_ARGS+=	--with-avahi
.else
CONFIGURE_ARGS+=	--without-avahi
.endif

.if ${PORT_OPTIONS:MFREEIPMI}
LIB_DEPENDS+=	libfreeipmi.so:${PORTSDIR}/sysutils/freeipmi
CONFIGURE_ARGS+=	--with-freeipmi
PLIST_SUB+=	NUT_FREEIPMI=""
.else
CONFIGURE_ARGS+=	--without-freeipmi
PLIST_SUB+=	NUT_FREEIPMI="@comment "
.endif

.if ${PORT_OPTIONS:MIPMIPSU}
LIB_DEPENDS+=	libfreeipmi.so:${PORTSDIR}/sysutils/freeipmi
CONFIGURE_ARGS+=	--with-ipmi
PLIST_SUB+=	NUT_IPMIPSU=""
.else
CONFIGURE_ARGS+=	--without-ipmi
PLIST_SUB+=	NUT_IPMIPSU="@comment "
.endif

.if ${PORT_OPTIONS:MOPENSSL}
USE_OPENSSL=	yes
CONFIGURE_ARGS+=	--with-openssl
.else
CONFIGURE_ARGS+=	--without-openssl --without-ssl
.endif

pre-install:
	@${MKDIR} ${STAGEDIR}${PREFIX}/libexec/nut
	@${REINPLACE_CMD} -e 's/device-name\*/cdev/g' ${WRKSRC}/scripts/devd/nut-usb.conf

post-install:
	@${MKDIR} ${STAGEDIR}${STATEDIR}
	${CP} ${STAGEDIR}${ETCDIR}/driver.list ${STAGEDIR}${PREFIX}/libexec/nut/
.if ${PORT_OPTIONS:MDOCS}
.if ${PORT_OPTIONS:MBASH}
	@${MKDIR} ${STAGEDIR}${PREFIX}/etc/bash_completion.d/
	${INSTALL_DATA} ${WRKSRC}/scripts/misc/nut.bash_completion ${STAGEDIR}${PREFIX}/etc/bash_completion.d/
.endif
	@${MKDIR} ${STAGEDIR}${DOCSDIR}/cables
	${INSTALL_DATA} ${WRKSRC}/docs/cables/*.txt ${STAGEDIR}${DOCSDIR}/cables
	${INSTALL_DATA} ${WRKSRC}/docs/*.txt ${STAGEDIR}${DOCSDIR}
	${INSTALL_DATA} ${WRKSRC}/docs/FAQ.txt ${STAGEDIR}${DOCSDIR}
.for file in AUTHORS COPYING ChangeLog INSTALL MAINTAINERS NEWS README UPGRADING
	${INSTALL_DATA} ${WRKSRC}/${file} ${STAGEDIR}${DOCSDIR}
.endfor
.endif

.include <bsd.port.mk>
