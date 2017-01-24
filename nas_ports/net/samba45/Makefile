PORTNAME?=		${SAMBA4_BASENAME}45
PORTVERSION?=		${SAMBA4_VERSION}
PORTREVISION?=		${REVISION}
CATEGORIES?=		net

MAINTAINER?=		john@ixsystems.com
COMMENT?=		Free SMB/CIFS and AD/DC server and client for Unix

LICENSE=		GPLv3

CONFLICTS?=		*samba3[2-6]-3.* samba4-4.0.* samba41-4.1.* samba42-4.2.* samba43-4.3.* samba44-4.4.*

SAMBA4_BASENAME=	samba
SAMBA4_PORTNAME=	${SAMBA4_BASENAME}4
SAMBA4_VERSION=		4.5.4
SAMBA4_DISTNAME=	${SAMBA4_BASENAME}-${SAMBA4_VERSION:S|.p|pre|:S|.r|rc|:S|.t|tp|:S|.a|alpha|}

NO_CHECKSUM=		yes
EXTRACT_ONLY=

WRKSRC=			/usr/samba_src

.if !defined(SAMBA4_SUBPORT)
CPE_VENDOR=		samba
CPE_PRODUCT=		samba
# Directories
VARDIR=			${DESTDIR}/var
SAMBA4_RUNDIR=		${VARDIR}/run/${SAMBA4_PORTNAME}
SAMBA4_LOGDIR=		${VARDIR}/log/${SAMBA4_PORTNAME}
SAMBA4_LOCKDIR=		${VARDIR}/db/${SAMBA4_PORTNAME}
SAMBA4_PRIVATEDIR=	${SAMBA4_LOCKDIR}/private
SAMBA4_LIBDIR=		${PREFIX}/lib
SAMBA4_MODULEDIR=	${SAMBA4_LIBDIR}/shared-modules
SAMBA4_INCLUDEDIR=	${PREFIX}/include/${SAMBA4_PORTNAME}
SAMBA4_CONFDIR=		${PREFIX}/etc
SAMBA4_CONFIG=		smb4.conf

CFLAGS=			-g -ggdb -gdwarf-2 -gstrict-dwarf -O0

CONFIGURE_ARGS+=	--mandir="${MANPREFIX}/man" \
			--sysconfdir="${SAMBA4_CONFDIR}" \
			--includedir="${SAMBA4_INCLUDEDIR}" \
			--datadir="${DATADIR}" \
			--libdir="${SAMBA4_LIBDIR}" \
			--with-pkgconfigdir="${PKGCONFIGDIR}" \
			--with-pammodulesdir="${SAMBA4_LIBDIR}" \
			--with-privatelibdir="${SAMBA4_LIBDIR}/samba" \
			--with-modulesdir="${SAMBA4_MODULEDIR}" \
			--localstatedir="${VARDIR}" \
			--with-piddir="${SAMBA4_RUNDIR}" \
			--with-sockets-dir="${SAMBA4_RUNDIR}" \
			--with-privileged-socket-dir="${SAMBA4_RUNDIR}" \
			--with-statedir="${SAMBA4_LOCKDIR}" \
			--with-cachedir="${SAMBA4_LOCKDIR}" \
			--with-privatedir="${SAMBA4_PRIVATEDIR}" \
			--with-logfilebase="${SAMBA4_LOGDIR}"
# Flags
CONFIGURE_ENV+=		PTHREAD_LDFLAGS="-lpthread"

USES=			cpe compiler waf pkgconfig perl5 python:2 \
			execinfo readline iconv shebangfix gettext zip
USE_PERL5=		build
USE_LDCONFIG=		${SAMBA4_LIBDIR}
WAF_CMD=		buildtools/bin/waf
CONFIGURE_LOG=		bin/config.log

PKGCONFIGDIR?=		${PREFIX}/libdata/pkgconfig
PLIST_SUB+=		PKGCONFIGDIR=${PKGCONFIGDIR:S;${PREFIX}/;;}

# XXX: Unconditional dependencies which can't be switched off(if present
# in the system)
# popt
LIB_DEPENDS+=		libpopt.so:${PORTSDIR}/devel/popt
# inotify
LIB_DEPENDS+=		libinotify.so:${PORTSDIR}/devel/libinotify
# SASL
LIB_DEPENDS+=		libsasl2.so:${PORTSDIR}/security/cyrus-sasl2
# GNUTLS
LIB_DEPENDS+=		libgcrypt.so:${PORTSDIR}/security/libgcrypt
LIB_DEPENDS+=		libgnutls.so:${PORTSDIR}/security/gnutls
# NFS4 ACL glue
LIB_DEPENDS+=		libsunacl.so:${PORTSDIR}/sysutils/libsunacl
# Libarchive
BUILD_DEPENDS+=		libarchive>=3.1.2:${PORTSDIR}/archivers/libarchive
RUN_DEPENDS+=		libarchive>=3.1.2:${PORTSDIR}/archivers/libarchive


# snapper needs dbus 
LIB_DEPENDS+=		libdbus-1.so:${PORTSDIR}/devel/dbus 
LIB_DEPENDS+=		libdbus-glib-1.so:${PORTSDIR}/devel/dbus-glib

# External Samba dependencies
# IDL compiler
BUILD_DEPENDS+=		p5-Parse-Pidl>=4.3.0:${PORTSDIR}/devel/p5-Parse-Pidl
# 
BUILD_DEPENDS+=		${PYTHON_PKGNAMEPREFIX}dnspython>=1.9.4:${PORTSDIR}/dns/py-dnspython
RUN_DEPENDS+=		${PYTHON_PKGNAMEPREFIX}dnspython>=1.9.4:${PORTSDIR}/dns/py-dnspython


# Using the bundled versions. Will make this conditional later.

# talloc
BUILD_DEPENDS+=		talloc>=2.1.8:${PORTSDIR}/devel/talloc
RUN_DEPENDS+=		talloc>=2.1.8:${PORTSDIR}/devel/talloc
SAMBA4_BUNDLED_LIBS+=	!talloc

# tevent
BUILD_DEPENDS+=		tevent>=0.9.31:${PORTSDIR}/devel/tevent
RUN_DEPENDS+=		tevent>=0.9.31:${PORTSDIR}/devel/tevent
SAMBA4_BUNDLED_LIBS+=	!tevent

# tdb
BUILD_DEPENDS+=		tdb>=1.3.12:${PORTSDIR}/databases/tdb
RUN_DEPENDS+=		tdb>=1.3.12:${PORTSDIR}/databases/tdb
SAMBA4_BUNDLED_LIBS+=	!tdb

# ntdb
BUILD_DEPENDS+=		ntdb>=1.0:${PORTSDIR}/databases/ntdb
RUN_DEPENDS+=		ntdb>=1.0:${PORTSDIR}/databases/ntdb
SAMBA4_BUNDLED_LIBS+=	!ntdb

# ldb
BUILD_DEPENDS+=		ldb>=1.1.29:${PORTSDIR}/databases/ldb
RUN_DEPENDS+=		ldb>=1.1.29:${PORTSDIR}/databases/ldb
SAMBA4_BUNDLED_LIBS+=	!ldb

# Don't use external libcom_err
#SAMBA4_BUNDLED_LIBS+=	com_err

PLIST_SUB+=		PY_DNSPYTHON="@comment "

SAMBA4_BUNDLED_LIBS+=	!libarchive
#SAMBA4_BUNDLED_LIBS+=	ALL
##############################################################################
# Options
OPTIONS_DEFINE=		ACL_SUPPORT AD_DC ADS AIO_SUPPORT CUPS DEBUG \
			CLUSTER DNSUPDATE DOCS FAM GLUSTERFS LDAP LIBZFS \
			PTHREADPOOL QUOTAS SPOTLIGHT SYSLOG UTMP

OPTIONS_DEFAULT:=	ACL_SUPPORT AD_DC ADS AIO_SUPPORT DEBUG \
			DNSUPDATE DOCS FAM LDAP \
			PTHREADPOOL QUOTAS SYSLOG UTMP

ACL_SUPPORT_DESC=	File system ACL support
AD_DC_DESC=		Active Directory Domain Controller support
ADS_DESC=		Active Directory client support
AIO_SUPPORT_DESC=	Asyncronous IO support
CLUSTER_DESC=	Cluster support
DEBUG_DESC=		With debug information in the binaries
DNSUPDATE_DESC=		Dynamic DNS update (require ADS)
EXP_MODULES_DESC=	Experimental modules
FAM_DESC=		File Alteration Monitor support
GLUSTERFS=		Gluster filesystem support
LDAP_DESC=		LDAP client support
LIBZFS_DESC=		LibZFS support
PTHREADPOOL_DESC=	Pthread pool
QUOTAS_DESC=		Disk quota support
SPOTLIGHT_DESC=	Spotlight support
UTMP_DESC=		UTMP accounting support
##############################################################################
OPTIONS_DEFINE+=	DEVELOPER MANPAGES EXP_MODULES

DEVELOPER_DESC=		With development support
MANPAGES_DESC=		Build manpages from DOCBOOK templates

OPTIONS_RADIO=		DNS ZEROCONF
OPTIONS_RADIO_DNS=	NSUPDATE BIND99 BIND910
OPTIONS_RADIO_ZEROCONF=	AVAHI MDNSRESPONDER

BIND99_DESC=		Use bind99 as AD DC DNS server frontend
BIND910_DESC=		Use bind910 as AD DC DNS server frontend
NSUPDATE_DESC=		Use samba NSUPDATE utility for AD DC

.include <bsd.port.options.mk>

CONFIGURE_ARGS+=	\
			--with-automount \
			--with-iconv \
			--with-libarchive \
			--with-pam \
			--with-regedit \
			--with-sendfile-support \
			--with-winbind \
			--without-fake-kaserver \
			--without-lttng \
			--without-profiling-data \
			--without-systemd \
			--enable-gnutls \
			--builtin-libraries=smbclient \
			--without-pie \
			${ICONV_CONFIGURE_BASE}

# for libexecinfo: (so that __builtin_frame_address() finds the top of the stack)
.if ${ARCH} == "amd64"
CFLAGS+=		-fno-omit-frame-pointer
.endif

.if ${PORT_OPTIONS:MBIND99}
RUN_DEPENDS+=		bind99>=9.9.0.0:${PORTSDIR}/dns/bind99
SUB_LIST+=		NSUPDATE="@comment "
.elif ${PORT_OPTIONS:MBIND910}
RUN_DEPENDS+=		bind910>=9.10.0.0:${PORTSDIR}/dns/bind910
SUB_LIST+=		NSUPDATE="@comment "
.elif ${PORT_OPTIONS:MNSUPDATE}
RUN_DEPENDS+=		samba-nsupdate:${PORTSDIR}/dns/samba-nsupdate
SUB_LIST+=		NSUPDATE=""
.endif

.if ${PORT_OPTIONS:MCLUSTER}
CONFIGURE_ARGS+=	--with-cluster-support
.else
CONFIGURE_ARGS+=	--without-cluster-support
.endif

.if ${PORT_OPTIONS:MDEBUG}
WITH_DEBUG=		yes
CONFIGURE_ARGS+=	--verbose
MAKE_ARGS+=		--verbose
CONFIGURE_ARGS+=	--enable-debug
.endif

# https://bugzilla.samba.org/show_bug.cgi?id=8969
.if ${PORT_OPTIONS:MDEVELOPER}
#GDB_CMD?=		gdb79
# https://bugs.freebsd.org/bugzilla/show_bug.cgi?id=194046
# XXX: Still may break, if the link isn't installed - blame devel/gdb maintainer then.
GDB_CMD?=		${LOCALBASE}/bin/gdb
BUILD_DEPENDS+=		${GDB_CMD}:${PORTSDIR}/devel/gdb
RUN_DEPENDS+=		${GDB_CMD}:${PORTSDIR}/devel/gdb
SAMBA4_MODULES+=	auth_skel perfcount_test pdb_test vfs_shadow_copy_test vfs_skel_opaque vfs_skel_transparent vfs_fake_acls
CONFIGURE_ARGS+=	--enable-developer --enable-selftest
PLIST_SUB+=		DEVELOPER=""
.else
GDB_CMD=		true
PLIST_SUB+=		DEVELOPER="@comment "
.endif
##############################################################################
# XXX: That will blow up your installation
# https://bugzilla.samba.org/show_bug.cgi?id=9302
.if defined(CRAZY)
WANT_EXP_MODULES=	auth_samba4 auth_script auth_skel auth_unix auth_wbc \
			gpext_registry gpext_scripts gpext_security idmap_ad \
			idmap_autorid idmap_hash idmap_ldap idmap_passdb \
			idmap_rid idmap_script idmap_tdb idmap_tdb2 idmap_nss \
			nss_info_template pdb_ldap pdb_samba_dsdb pdb_smbpasswd \
			pdb_tdbsam pdb_test pdb_wbc_sam perfcount_test vfs_acl_tdb \
			vfs_acl_xattr vfs_aio_fork vfs_aio_posix \
			vfs_aio_pthread vfs_audit vfs_cacheprime vfs_cap \
			vfs_catia vfs_commit vfs_crossrename vfs_default_quota \
			vfs_dfs_samba4 vfs_dirsort vfs_expand_msdfs vfs_extd_audit \
			vfs_fake_acls vfs_fake_perms vfs_full_audit vfs_media_harmony \
			vfs_netatalk vfs_posix_eadb vfs_preopen vfs_readahead \
			vfs_readonly vfs_recycle vfs_shadow_copy vfs_shadow_copy2 \
			vfs_shadow_copy_test vfs_shell_snap vfs_skel_opaque \
			vfs_skel_transparent vfs_streams_depot vfs_streams_xattr \
			vfs_syncops vfs_time_audit vfs_unityed_media vfs_xattr_tdb \
			vfs_winmsa vfs_zfsacl vfs_zfs_space
.endif

.if ${PORT_OPTIONS:MEXP_MODULES}
.	if !defined(WANT_EXP_MODULES) || empty(WANT_EXP_MODULES)
WANT_EXP_MODULES=	vfs_cacheprime gpext_scripts gpext_security gpext_registry
.	endif
.endif

.if ${PORT_OPTIONS:MACL_SUPPORT}
LIB_DEPENDS+=		libsunacl.so:${PORTSDIR}/sysutils/libsunacl
WANT_EXP_MODULES+=	vfs_zfsacl
SAMBA4_MODULES+=	vfs_zfsacl
CONFIGURE_ARGS+=	--with-acl-support
.else
CONFIGURE_ARGS+=	--without-acl-support
.endif

.if ! ${PORT_OPTIONS:MAD_DC}
CONFIGURE_ARGS+=	--without-ad-dc
PLIST_SUB+=		AD_DC="@comment "
.else
PLIST_SUB+=		AD_DC=""
.endif

.if ${PORT_OPTIONS:MADS}
SAMBA4_WANT_ADS=	yes
SAMBA4_WANT_LDAP=	yes
# List of extra modules taken from RHEL build
# https://bugs.freebsd.org/bugzilla/show_bug.cgi?id=197320
SAMBA4_MODULES+=	idmap_rid idmap_ad idmap_hash idmap_adex idmap_tdb2
.endif

.if ${PORT_OPTIONS:MAVAHI}
LIB_DEPENDS+=		libavahi-client.so:${PORTSDIR}/net/avahi-app
CONFIGURE_ARGS+=	--enable-avahi
.else
CONFIGURE_ARGS+=	--disable-avahi
.endif

.if ${PORT_OPTIONS:MMDNSRESPONDER}
LIB_DEPENDS+=		libdns_sd.so:${PORTSDIR}/net/mDNSResponder
CONFIGURE_ARGS+=	--enable-dnssd
.else
CONFIGURE_ARGS+=	--disable-dnssd
.endif

.if ${PORT_OPTIONS:MCUPS}
LIB_DEPENDS+=		libcups.so:${PORTSDIR}/print/cups-client
CONFIGURE_ARGS+=	--enable-cups --enable-iprint
.else
CONFIGURE_ARGS+=	--disable-cups --disable-iprint
.endif

.if ${PORT_OPTIONS:MDNSUPDATE}
SAMBA_WANT_ADS=		yes
CONFIGURE_ARGS+=	--with-dnsupdate
.else
CONFIGURE_ARGS+=	--without-dnsupdate
.endif

# https://bugzilla.samba.org/show_bug.cgi?id=9545
.if ${PORT_OPTIONS:MFAM}
USES+=			fam
CONFIGURE_ARGS+=	--with-fam
.else
CONFIGURE_ARGS+=	--without-fam
.endif

.if ${PORT_OPTIONS:MGLUSTERFS}
CONFIGURE_ARGS+=	--enable-glusterfs
.else
CONFIGURE_ARGS+=	--disable-glusterfs
.endif

.if ${PORT_OPTIONS:MLDAP}
SAMBA4_WANT_LDAP=	yes
.endif

.if ${PORT_OPTIONS:MLIBZFS}
CONFIGURE_ARGS+=	--with-libzfs
WANT_EXP_MODULES+=	vfs_zfs_space
SAMBA4_MODULES+=	vfs_zfs_space
PLIST_SUB+=		LIBZFS=""
.else
CONFIGURE_ARGS+=	--without-libzfs
PLIST_SUB+=		LIBZFS="@comment "
.endif

.if ${PORT_OPTIONS:MPTHREADPOOL}
CONFIGURE_ARGS+=	--enable-pthreadpool
SAMBA4_MODULES+=	vfs_aio_pthread
.else
CONFIGURE_ARGS+=	--disable-pthreadpool
.endif

.if ${PORT_OPTIONS:MQUOTAS}
CONFIGURE_ARGS+=	--with-quotas
.else
CONFIGURE_ARGS+=	--without-quotas
.endif

.if ${PORT_OPTIONS:MSPOTLIGHT}
BUILD_DEPENDS+=	tracker>=1.4.1:${PORTSDIR}/sysutils/tracker
RUN_DEPENDS+=	tracker>=1.4.1:${PORTSDIR}/sysutils/tracker
CONFIGURE_ARGS+=	--enable-spotlight
.else
CONFIGURE_ARGS+=	--disable-spotlight
.endif

.if ${PORT_OPTIONS:MSYSLOG}
CONFIGURE_ARGS+=	--with-syslog
.else
CONFIGURE_ARGS+=	--without-syslog
.endif

.if ${PORT_OPTIONS:MUTMP}
CONFIGURE_ARGS+=	--with-utmp
.else
CONFIGURE_ARGS+=	--without-utmp
.endif

.if defined(SAMBA4_WANT_ADS)
CONFIGURE_ARGS+=	--with-ads
.else
CONFIGURE_ARGS+=	--without-ads
.endif

.if defined(SAMBA4_WANT_LDAP)
USE_OPENLDAP=		yes
#WANT_OPENLDAP_SASL=	yes
CONFIGURE_ARGS+=	--with-ldap
PLIST_SUB+=		LDAP=""
.else
CONFIGURE_ARGS+=	--without-ldap
PLIST_SUB+=		LDAP="@comment "
.endif

.if ! ${PORT_OPTIONS:MMANPAGES}
CONFIGURE_ENV+=		XSLTPROC=""
.else
BUILD_DEPENDS+=		${LOCALBASE}/share/xsl/docbook/manpages/docbook.xsl:${PORTSDIR}/textproc/docbook-xsl \
			xsltproc:${PORTSDIR}/textproc/libxslt
.endif

.if defined(SAMBA4_BUNDLED_LIBS) && !empty(SAMBA4_BUNDLED_LIBS)
CONFIGURE_ARGS+=	--bundled-libraries="${SAMBA4_BUNDLED_LIBS:Q:C|(\\\\ )+|,|g:S|\\||g}"
.endif

.if defined(WANT_EXP_MODULES) && !empty(WANT_EXP_MODULES)
SAMBA4_MODULES+=	${WANT_EXP_MODULES}
.endif

.if defined(SAMBA4_MODULES) && !empty(SAMBA4_MODULES)
CONFIGURE_ARGS+=	--with-shared-modules="${SAMBA4_MODULES:Q:C|(\\\\ )+|,|g:S|\\||g}"
.endif
# XXX: Dirty
.for module in	auth_samba4 auth_skel auth_unix auth_wbc gpext_registry gpext_scripts \
		gpext_security idmap_ad idmap_ldap idmap_nss idmap_passdb idmap_tdb \
		nss_info_template pdb_ldap pdb_samba_dsdb pdb_smbpasswd pdb_tdbsam \
		pdb_test pdb_wbc_sam perfcount_test vfs_aio_posix vfs_aio_pthread \
		vfs_cacheprime vfs_dfs_samba4 vfs_fake_acls \
		vfs_shadow_copy_test vfs_skel_opaque vfs_skel_transparent
.	if !empty(SAMBA4_MODULES) && ${SAMBA4_MODULES:M${module}}
PLIST_SUB+=		MODULE_${module:tu}=""
.	else
PLIST_SUB+=		MODULE_${module:tu}="@comment "
.	endif
.endfor
##############################################################################
# !SAMBA4_SUBPORT
.endif

.include <bsd.port.pre.mk>

checksum extract fetch:
	${ECHO_CMD} ${.TARGET} not needed because building direct

.if !defined(SAMBA4_SUBPORT)

SAMBA4_SUB=		SAMBA4_LOGDIR="${SAMBA4_LOGDIR}" \
			SAMBA4_RUNDIR="${SAMBA4_RUNDIR}" \
			SAMBA4_LOCKDIR="${SAMBA4_LOCKDIR}" \
			SAMBA4_MODULEDIR="${SAMBA4_MODULEDIR}" \
			SAMBA4_PRIVATEDIR="${SAMBA4_PRIVATEDIR}" \
			SAMBA4_CONFDIR="${SAMBA4_CONFDIR}" \
			SAMBA4_CONFIG="${SAMBA4_CONFIG}"

PLIST_SUB+=		${SAMBA4_SUB}
SUB_LIST+=		${SAMBA4_SUB}

USE_RC_SUBR=		samba_server
SUB_FILES=		pkg-message README.FreeBSD
# Make sure that the right version of Python is used by the tools
# https://bugzilla.samba.org/show_bug.cgi?id=7305
python_OLD_CMD=		/usr/bin/env python
SHEBANG_FILES=		${PATCH_WRKSRC}/source4/scripting/bin/*
# No fancy color error messages
.if ${COMPILER_TYPE} == "clang"
CFLAGS+=		-fno-color-diagnostics
.endif
CONFIGURE_ENV+=		NOCOLOR=yes WAF_LOG_FORMAT='%(c1)s%(zone)s%(c2)s %(message)s'
MAKE_ENV+=		NOCOLOR=yes WAF_LOG_FORMAT='%(c1)s%(zone)s%(c2)s %(message)s'

SAMBA_MAN1+=		dbwrap_tool.1 findsmb.1 gentest.1 locktest.1 \
			log2pcap.1 masktest.1 ndrdump.1 nmblookup.1 \
			nmblookup4.1 ntlm_auth.1 oLschema2ldif.1 \
			profiles.1 regdiff.1 regpatch.1 regshell.1 \
			regtree.1 rpcclient.1 sharesec.1 smbcacls.1 \
			smbclient.1 smbcontrol.1 smbcquotas.1 smbget.1 \
			smbstatus.1 smbtar.1 smbtorture.1 smbtree.1 \
			testparm.1 vfstest.1 wbinfo.1

SAMBA_MAN5+=		lmhosts.5 smbgetrc.5 smbpasswd.5 pam_winbind.conf.5 \
			smb.conf.5

SAMBA_MAN7+=		samba.7 winbind_krb5_locator.7

SAMBA_MAN8+=		cifsdd.8 eventlogadm.8 idmap_ad.8 idmap_autorid.8 idmap_hash.8 \
			idmap_ldap.8 idmap_nss.8 idmap_rfc2307.8 idmap_rid.8 \
			idmap_tdb.8 idmap_tdb2.8 net.8 nmbd.8 pam_winbind.8 pdbedit.8 \
			samba-regedit.8 samba-tool.8 samba.8 smbd.8 smbpasswd.8 \
			smbspool_krb5_wrapper.8 smbspool.8 smbta-util.8 vfs_acl_tdb.8 vfs_acl_xattr.8 \
			vfs_aio_fork.8 vfs_aio_linux.8 vfs_aio_pthread.8 \
			vfs_audit.8 vfs_cacheprime.8 vfs_cap.8 vfs_catia.8 vfs_ceph.8 \
			vfs_commit.8 vfs_crossrename.8 vfs_default_quota.8 \
			vfs_dirsort.8 vfs_extd_audit.8 vfs_fake_perms.8 vfs_fileid.8 \
			vfs_fruit.8 vfs_full_audit.8 vfs_glusterfs.8 vfs_gpfs.8 vfs_media_harmony.8 \
			vfs_netatalk.8 vfs_offline.8 vfs_prealloc.8 \
			vfs_preopen.8 vfs_readahead.8 vfs_readonly.8 \
			vfs_recycle.8 vfs_scannedonly.8 vfs_shadow_copy.8 \
			vfs_shadow_copy2.8 vfs_snapper.8 vfs_smb_traffic_analyzer.8 \
			vfs_streams_depot.8 vfs_streams_xattr.8 vfs_syncops.8 vfs_time_audit.8 \
			vfs_tsmsm.8 vfs_worm.8 vfs_xattr_tdb.8 winbindd.8 \
			vfs_linux_xfs_sgid.8 vfs_btrfs.8 vfs_shell_snap.8 vfs_unityed_media.8

PORTDOCS=		README.FreeBSD

IGNORE_NONTHREAD_PYTHON=needs port lang/python${PYTHON_SUFFIX} to be build with THREADS support


post-extract:
			@${RM} -rf ${WRKSRC}/pidl

post-patch:
			@${REINPLACE_CMD} -e 's|$${PKGCONFIGDIR}|${PKGCONFIGDIR}|g' \
				${PATCH_WRKSRC}/buildtools/wafsamba/pkgconfig.py
			@${REINPLACE_CMD} -e 's|%%LOCALBASE%%|${LOCALBASE}|g' \
				${PATCH_WRKSRC}/buildtools/wafsamba/samba_pidl.py \
				${PATCH_WRKSRC}/buildtools/wafsamba/wafsamba.py
			@${REINPLACE_CMD} -e 's|%%GDB_CMD%%|${GDB_CMD}|g' \
				${PATCH_WRKSRC}/buildtools/scripts/abi_gen.sh
			@${REINPLACE_CMD} -e 's|%%SAMBA4_CONFIG%%|${SAMBA4_CONFIG}|g' \
				${PATCH_WRKSRC}/dynconfig/wscript

# Use threading (or multiprocessing) but not thread (renamed in python 3+).
pre-configure:
			@if ! ${PYTHON_CMD} -c "import multiprocessing;" 2>/dev/null; then \
				${ECHO_CMD}; \
				${ECHO_MSG} "===>  ${PKGNAME} "${IGNORE_NONTHREAD_PYTHON:Q}.; \
				${ECHO_CMD}; \
				${FALSE}; \
			fi

# XXX: Gross hack to allow build newer Samba while old one is installed.
# This implies that LINKFLAGS_PYEMBED contains flags which are already
# used in other parts of LINKFLAGS, namely -L$(LOCALBASE)/lib and -pthread
post-configure:
	-${REINPLACE_CMD} -e 's|LINKFLAGS_PYEMBED.*|LINKFLAGS_PYEMBED = []|' \
		${CONFIGURE_WRKSRC}/bin/c4che/default.cache.py

pre-build:
.if ! ${PORT_OPTIONS:MMANPAGES}
.	for man in	libcli/nbt/man/nmblookup4.1 \
			librpc/tools/ndrdump.1 \
			source4/lib/registry/man/regdiff.1 \
			source4/lib/registry/man/regpatch.1 \
			source4/lib/registry/man/regshell.1 \
			source4/lib/registry/man/regtree.1 \
			source4/torture/man/gentest.1 \
			source4/torture/man/locktest.1 \
			source4/torture/man/masktest.1 \
			source4/torture/man/smbtorture.1 \
			source4/utils/man/ntlm_auth4.1 \
			source4/utils/man/oLschema2ldif.1
			-@${MKDIR} `dirname ${BUILD_WRKSRC}/bin/default/${man}`
			${INSTALL_MAN} ${FILESDIR}/man/`basename ${man}` ${BUILD_WRKSRC}/bin/default/${man}
.	endfor
			-@${MKDIR} ${BUILD_WRKSRC}/bin/default/docs-xml/manpages
.	for man in ${SAMBA_MAN1} ${SAMBA_MAN5} ${SAMBA_MAN7} ${SAMBA_MAN8}
			-${INSTALL_MAN} ${BUILD_WRKSRC}/docs/manpages/${man} ${BUILD_WRKSRC}/bin/default/docs-xml/manpages
.	endfor
.endif

post-install:
			@${LN} -sf smb.conf.5.gz ${STAGEDIR}${PREFIX}/man/man5/smb4.conf.5.gz
.if ${PORT_OPTIONS:MDOCS}
			@${MKDIR} ${STAGEDIR}${DOCSDIR}
.	for doc in ${PORTDOCS}
			@${INSTALL_DATA} ${WRKDIR}/${doc} ${STAGEDIR}${DOCSDIR}
.	endfor
.endif
# Run post-install script
.for dir in ${SAMBA4_LOGDIR} ${SAMBA4_RUNDIR} ${SAMBA4_LOCKDIR} ${SAMBA4_MODULEDIR}
			@${INSTALL} -d -m 0755 "${STAGEDIR}${dir}"
.endfor
			@${INSTALL} -d -m 0700 "${STAGEDIR}${SAMBA4_PRIVATEDIR}"
.for dir in auth bind9 gensec gpext idmap ldb nss_info pdb perfcount process_model service vfs
			@${MKDIR} "${STAGEDIR}${SAMBA4_MODULEDIR}/${dir}"
.endfor

.if ${PORT_OPTIONS:MDEVELOPER}
test: build
			@(cd ${INSTALL_WRKSRC} && ${SETENV} ${MAKE_ENV} ${PYTHON_CMD} ${INSTALL_WRKSRC}/${WAF_CMD} ${MAKE_ARGS} $@)
.endif

# !SAMBA4_SUBPORT
.endif

.include <bsd.port.post.mk>
