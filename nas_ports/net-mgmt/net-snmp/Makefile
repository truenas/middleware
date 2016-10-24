# Created by: gpalmer
# $FreeBSD$

PORTNAME=	snmp
PORTVERSION=	5.7.3
PORTREVISION=	12
CATEGORIES=	net-mgmt ipv6
MASTER_SITES=	SF/net-${PORTNAME}/net-${PORTNAME}/${PORTVERSION}
PKGNAMEPREFIX=	net-
DISTNAME=	${PKGNAMEPREFIX}${PORTNAME}-${PORTVERSION}

MAINTAINER=	zi@FreeBSD.org
COMMENT=	Extendable SNMP implementation

LICENSE=	BSD3CLAUSE
LICENSE_FILE=	${WRKSRC}/COPYING

OPTIONS_DEFINE=	IPV6 MFD_REWRITES PERL PERL_EMBEDDED PYTHON DUMMY TKMIB \
		MYSQL AX_SOCKONLY UNPRIVILEGED SMUX DOCS JAIL AX_DISABLE_TRAP
OPTIONS_DEFAULT=PERL PERL_EMBEDDED DUMMY SMUX

MFD_REWRITES_DESC=	Build with 64-bit Interface Counters
PERL_EMBEDDED_DESC=	Build embedded perl
DUMMY_DESC=		Enable dummy values as placeholders
TKMIB_DESC=		Install graphical MIB browser
#DMALLOC_DESC=		Enable dmalloc debug memory allocator
AX_SOCKONLY_DESC=	Disable UDP/TCP transports for agentx
AX_DISABLE_TRAP_DESC=	Disable agentx subagent code in snmptrapd
UNPRIVILEGED_DESC=	Allow unprivileged users to execute net-snmp
SMUX_DESC=		Build with SNMP multiplexing (SMUX) support
JAIL_DESC=		Options for running snmpd within a jail(8)

MAKE_JOBS_UNSAFE=	yes

PORTSCOUT=	skipv:5.7.2.1

GNU_CONFIGURE=	yes
USE_RC_SUBR=	snmpd snmptrapd
USE_OPENSSL=	yes
USE_LDCONFIG=	yes
USES=		cpe libtool perl5
CPE_VENDOR=	net-snmp
USE_PERL5=	build run
USE_CSTD=	c99

CFLAGS+=	-I${LOCALBASE}/include -I${PKG_PREFIX}/include
LDFLAGS+=	-L${LOCALBASE}/lib
CONFIGURE_ENV+=	PERLPROG="${PERL}" PSPROG="${PS_CMD}" SED="${SED}"
CONFIGURE_ARGS+=--enable-shared --enable-internal-md5 \
		--with-default-snmp-version="${DEFAULT_SNMP_VERSION}" \
		--with-sys-contact="${NET_SNMP_SYS_CONTACT}" \
		--with-sys-location="${NET_SNMP_SYS_LOCATION}" \
		--with-logfile="${NET_SNMP_LOGFILE}" \
		--with-persistent-directory="${NET_SNMP_PERSISTENTDIR}" \
		--with-gnu-ld --with-libwrap \
		--with-ldflags="-lm -lkvm -ldevstat -L${PKG_PREFIX}/lib -L${LOCALBASE}/lib ${LCRYPTO}"
SUB_FILES=	pkg-message

.if !defined(WITHOUT_SSP)
CONFIGURE_ARGS+=--with-libs="-lssp_nonshared"
.endif

.if defined(BATCH)
CONFIGURE_ARGS+=--with-defaults
.endif

.include <bsd.port.options.mk>

.if ${PORT_OPTIONS:MPYTHON}
PYDISTUTILS_PKGNAME?=		netsnmp-python
PYDISTUTILS_PKGVERSION?=	1.0a1
USES+=		python
RUN_DEPENDS+=	${PYTHON_PKGNAMEPREFIX}setuptools${PYTHON_SUFFIX}>0:devel/py-setuptools${PYTHON_SUFFIX}
BUILD_DEPENDS+=	${PYTHON_PKGNAMEPREFIX}setuptools${PYTHON_SUFFIX}>0:devel/py-setuptools${PYTHON_SUFFIX}
CONFIGURE_ARGS+=--with-python-modules
CONFIGURE_ENV+=	PYTHONPROG="${PYTHON_CMD}"
MAKE_ENV+=	PYDISTUTILS_INSTALLARGS="${PYDISTUTILS_INSTALLARGS}" STAGEDIR="${STAGEDIR}"
PLIST_SUB+=	WITH_PYTHON="" PYTHON_VER=${PYTHON_VER}
PLIST_SUB+=	PYDISTUTILS_PKGVERSION=${PYDISTUTILS_PKGVERSION}
.else
PLIST_SUB+=	WITH_PYTHON="@comment "
.endif

CONFIGURE_ARGS+=--with-openssl="${OPENSSLBASE}"

.if ${PORT_OPTIONS:MDUMMY}
CONFIGURE_ARGS+=--with-dummy-values
.endif

.if ! ${PORT_OPTIONS:MTKMIB}
EXTRA_PATCHES+=	${PATCHDIR}/extra-patch-local_Makefile.in
PLIST_SUB+=	WITH_TKMIB="@comment "
.else
RUN_DEPENDS+=	p5-Tk>=0:x11-toolkits/p5-Tk
PLIST_SUB+=	WITH_TKMIB=""
.endif

.if ${PORT_OPTIONS:MPERL}
CONFIGURE_ARGS+=--with-perl-modules
.if ! ${PORT_OPTIONS:MPERL_EMBEDDED}
CONFIGURE_ARGS+=--disable-embedded-perl
PLIST_SUB+=	WITH_PERL_EMBEDDED="@comment "
.else
CONFIGURE_ARGS+=--enable-embedded-perl
PLIST_SUB+=	WITH_PERL_EMBEDDED=""
.endif
PLIST_SUB+=	WITH_PERL=""
.else
USE_PERL5=	build
CONFIGURE_ARGS+=--disable-embedded-perl --without-perl-modules
PLIST_SUB+=	WITH_PERL_EMBEDDED="@comment "
PLIST_SUB+=	WITH_PERL="@comment "
.endif

#.if ${PORT_OPTIONS:MDMALLOC}
#LIB_DEPENDS+=	libdmalloc.so:devel/dmalloc
#CONFIGURE_ARGS+=--with-dmalloc=${LOCALBASE}
#.else
#CONFIGURE_ARGS+=--without-dmalloc
#.endif

.if ${PORT_OPTIONS:MMYSQL}
USE_MYSQL=	yes
CONFIGURE_ARGS+=--with-mysql
CONFIGURE_ENV+=	MYSQLCONFIG=${LOCALBASE}/bin/mysql_config
.endif

.if ${PORT_OPTIONS:MAX_DISABLE_TRAP}
CONFIGURE_ARGS+=--disable-snmptrapd-subagent
.endif

.if ${PORT_OPTIONS:MAX_SOCKONLY}
CONFIGURE_ARGS+=--enable-agentx-dom-sock-only
.endif

.if ${PORT_OPTIONS:MIPV6}
CONFIGURE_ARGS+=--enable-ipv6
# --with-transport="UDPIPv6 TCPIPv6" --with-modules=mibII/ipv6"
PLIST_SUB+=	WITH_IPV6=""
.else
PLIST_SUB+=	WITH_IPV6="@comment "
.endif

.if ${PORT_OPTIONS:MUNPRIVILEGED}
CONFIGURE_ARGS+=--without-root-access
.endif

SHLIB_VERSION=	30
SHLIB_VERSION2=	.0.3
PLIST_SUB+=	SHLIB_VERSION=${SHLIB_VERSION} SHLIB_VERSION2=${SHLIB_VERSION2}
SCRIPTS_SUB=	PREFIX=${PREFIX} PERL=${PERL}

DEFAULT_SNMP_VERSION?=	3
NET_SNMP_SYS_CONTACT?=	nobody@nowhere.invalid
NET_SNMP_SYS_LOCATION?=	somewhere
NET_SNMP_LOGFILE?=	/var/log/snmpd.log
NET_SNMP_PERSISTENTDIR?=/var/net-snmp
NET_SNMP_WITH_MIB_MODULE_LIST+=	host disman/event-mib mibII/mta_sendmail mibII/tcpTable ucd-snmp/diskio sctp-mib

.if ${OSVERSION} >= 1000000 && ${OSVERSION} < 1100062
CFLAGS+=	-D_WANT_IFADDR
.endif

.if ${OSVERSION} >= 1100062
NET_SNMP_WITHOUT_MIB_MODULE_LIST+=	mibII/ipv6
.endif

.if ${PORT_OPTIONS:MMFD_REWRITES}
CONFIGURE_ARGS+=--enable-mfd-rewrites
NET_SNMP_WITH_MIB_MODULE_LIST+=	if-mib
.endif

.if ${PORT_OPTIONS:MJAIL}
NET_SNMP_WITHOUT_MIB_MODULE_LIST+=	host
NET_SNMP_WITHOUT_MIB_MODULE_LIST+=	ucd-snmp/memory
CONFIGURE_ARGS+=			--without-kmem-usage
.endif

.if ${PORT_OPTIONS:MSMUX}
NET_SNMP_WITH_MIB_MODULE_LIST+=		smux
.else
NET_SNMP_WITHOUT_MIB_MODULE_LIST+=	smux
.endif

.if defined(NET_SNMP_WITH_MIB_MODULE_LIST) && \
    !empty(NET_SNMP_WITH_MIB_MODULE_LIST)
CONFIGURE_ARGS+=--with-mib-modules="${NET_SNMP_WITH_MIB_MODULE_LIST}"
.endif

.if defined(NET_SNMP_WITHOUT_MIB_MODULE_LIST) && \
    !empty(NET_SNMP_WITHOUT_MIB_MODULE_LIST)
CONFIGURE_ARGS+=--with-out-mib-modules="${NET_SNMP_WITHOUT_MIB_MODULE_LIST}"
.endif

BIN_FILES=	snmpbulkwalk snmpget snmpgetnext snmpset \
		snmpstatus snmptest snmptranslate snmptrap snmpwalk \
		snmptable snmpbulkget snmpdelta snmpdf agentxtrap \
		snmpvacm snmpusm encode_keychange snmpnetstat
LIB_FILES=	libnetsnmp.so.${SHLIB_VERSION}${SHLIB_VERSION2} \
		libnetsnmpagent.so.${SHLIB_VERSION}${SHLIB_VERSION2} \
		libnetsnmpmibs.so.${SHLIB_VERSION}${SHLIB_VERSION2} \
		libnetsnmphelpers.so.${SHLIB_VERSION}${SHLIB_VERSION2} \
		libnetsnmptrapd.so.${SHLIB_VERSION}${SHLIB_VERSION2}
SBIN_FILES=	snmpd snmptrapd
STARTUP_DIR=	${PREFIX}/etc/rc.d
SCRIPT_FILES=	snmpcheck.def mib2c fixproc ipf-mod.pl traptoemail
.if ${PORT_OPTIONS:MTKMIB}
SCRIPT_FILES+=	tkmib
.endif
DOC_FILES=	AGENT.txt COPYING FAQ NEWS README \
		README.agentx README.krb5 README.snmpv3 README.thread \
		agent/mibgroup/README.smux

CONFLICTS=	ucd-snmp-4.* net-snmp-5.3.*

.include <bsd.port.pre.mk>

.if defined(WITH_OPENSSL_PORT) || defined(OPENSSL_PORT)
LCRYPTO=	-lcrypto
.else
LCRYPTO=
.endif

pre-everything::
	@${ECHO_MSG}
	@${ECHO_MSG} "You may use the following build options:"
	@${ECHO_MSG}
	@${ECHO_MSG} "DEFAULT_SNMP_VERSION=\"3\"	Default version of SNMP to use."
	@${ECHO_MSG} "NET_SNMP_SYS_CONTACT=\"${NET_SNMP_SYS_CONTACT}\""
	@${ECHO_MSG} "				Default system contact."
	@${ECHO_MSG} "NET_SNMP_SYS_LOCATION=\"${NET_SNMP_SYS_LOCATION}\""
	@${ECHO_MSG} "				Default system location."
	@${ECHO_MSG} "NET_SNMP_LOGFILE=\"${NET_SNMP_LOGFILE}\""
	@${ECHO_MSG} "				Default log file location for snmpd."
	@${ECHO_MSG} "NET_SNMP_PERSISTENTDIR=\"${NET_SNMP_PERSISTENTDIR}\""
	@${ECHO_MSG} "				Default directory for persistent data storage."
	@${ECHO_MSG} "NET_SNMP_WITH_MIB_MODULE_LIST=\"${NET_SNMP_WITH_MIB_MODULE_LIST}\""
	@${ECHO_MSG} "                             MIBs to add to the build."
	@${ECHO_MSG} "NET_SNMP_WITHOUT_MIB_MODULE_LIST=\"${NET_SNMP_WITHOUT_MIB_MODULE_LIST}\""
	@${ECHO_MSG} "                             MIBs to omit from the build."
	@${ECHO_MSG}

post-patch:
.for filename in ${SCRIPT_FILES}
	@${REINPLACE_CMD} -e 's|/usr/local|${PREFIX}|' ${WRKSRC}/local/${filename}
.endfor
	@${REINPLACE_CMD} -e 's!utmp_p->ut_name!utmp_p->ut_user!' \
	    ${WRKSRC}/agent/mibgroup/host/hr_system.c
	@${REINPLACE_CMD} -E -e 's|return pci_lookup_name|disabled broken|g' \
		${WRKSRC}/configure

post-configure:
	@${FIND} ${WRKSRC} -name Makefile | \
		${XARGS} ${REINPLACE_CMD} -E -e '/^INSTALL[ 	]+=/s|$$| -m 755|'
.for hdr in sys/mbuf.h netinet/in_pcb.h netinet/in_var.h netinet/ip6.h pkg.h
	@${REINPLACE_CMD} -E -e '\
		s!^.*#undef.*(HAVE_${hdr:tu:S/./_/g:S/\//_/g}).*$$!#define \1 1!g' \
			${WRKSRC}/include/net-snmp/net-snmp-config.h
.endfor
.if ${PORT_OPTIONS:MPYTHON}
	@(cd ${WRKSRC}/python; \
	${SETENV} ${MAKE_ENV} ${PYTHON_CMD} ${PYSETUP} setopt -c bdist_egg \
		-o plat-name -s "" --basedir=${WRKSRC}; \
	${SETENV} ${MAKE_ENV} ${PYTHON_CMD} ${PYSETUP} setopt -c bdist \
		-o plat-name -s "" --basedir=${WRKSRC})
.endif

post-build:
.if ${PORT_OPTIONS:MPERL}
	${FIND} ${WRKSRC}/perl -name Makefile | \
	${XARGS} ${REINPLACE_CMD} -E -e '\
		s!^(PREFIX) = .*!\1 = ${PREFIX}!; \
		s!^(INSTALLMAN3DIR|INSTALLSITEMAN3DIR) = .*!\1 = ${PREFIX}/man/man3!; \
		s!^(INSTALLSITELIB|INSTALLSITEARCH) = /usr/local/(.*)!\1 = ${PREFIX}/\2!; \
		s! doc_(perl|site|\$$\(INSTALLDIRS\))_install$$!!; \
		'
.else
	${REINPLACE_CMD} -e 's| perlinstall||' ${WRKSRC}/Makefile
.endif

post-install: strip-files install-config-files install-doc-files
	@${MKDIR} ${STAGEDIR}/var/agentx ${STAGEDIR}${PREFIX}/etc/newsyslog.conf.d
	@(cd ${STAGEDIR}${PREFIX}/lib && ${LN} -sf libnetsnmp.so.${SHLIB_VERSION} libnetsnmp.so)
	@(cd ${STAGEDIR}${PREFIX}/lib && ${LN} -sf libnetsnmpagent.so.${SHLIB_VERSION} libnetsnmpagent.so)
	@(cd ${STAGEDIR}${PREFIX}/lib && ${LN} -sf libnetsnmphelpers.so.${SHLIB_VERSION} libnetsnmphelpers.so)
	@(cd ${STAGEDIR}${PREFIX}/lib && ${LN} -sf libnetsnmpmibs.so.${SHLIB_VERSION} libnetsnmpmibs.so)
	@(cd ${STAGEDIR}${PREFIX}/lib && ${LN} -sf libnetsnmptrapd.so.${SHLIB_VERSION} libnetsnmptrapd.so)
	${INSTALL_DATA} ${FILESDIR}/net-snmp.conf ${STAGEDIR}${PREFIX}/etc/newsyslog.conf.d/

strip-files:
	(cd ${STAGEDIR}${PREFIX}/bin; ${STRIP_CMD} ${BIN_FILES})
	(cd ${STAGEDIR}${PREFIX}/lib; ${STRIP_CMD} ${LIB_FILES})
	(cd ${STAGEDIR}${PREFIX}/sbin; ${STRIP_CMD} ${SBIN_FILES})

install-config-files:
	${INSTALL_DATA} ${WRKSRC}/EXAMPLE.conf ${STAGEDIR}${DATADIR}/snmpd.conf.example

install-doc-files:
.if ${PORT_OPTIONS:MDOCS}
	@${MKDIR} ${STAGEDIR}${DOCSDIR}
. for filename in ${DOC_FILES}
	${INSTALL_DATA} ${WRKSRC}/${filename} ${STAGEDIR}${DOCSDIR}
. endfor
.endif

# Maintainer's note:
#   Don't forget to bump library version in these ports.
#   french/plgrenouille,graphics/hpoj,lang/php4,lang/php5,mail/cyrus-imapd22,mail/cyrus-imapd23,misc/kdeutils3,net-mgmt/braa,net-mgmt/docsis,net-mgmt/mbrowse,net-mgmt/nagios-snmp-plugins,net-mgmt/p5-SNMP-Info,net-mgmt/py-yapsnmp,net-mgmt/sdig,net-mgmt/zabbix,net/cactid,net/wireshark,net/ifstat,net/quagga,net/rtg,print/hplip,security/libfwbuilder,sysutils/apcupsd,sysutils/jailadmin,sysutils/nut

.include <bsd.port.post.mk>
