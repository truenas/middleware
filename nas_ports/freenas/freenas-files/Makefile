#
# $FreeBSD$
# $Id$
#

PORTNAME=       freenas-files
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        miscellaneous files for FreeNAS

USE_XZ=		yes

PREFIX=/

# explicitly set this for the port build
FREEBSD_SRCTOP=/usr/src
PLIST_SUB=	MACHINE_ARCH=${MACHINE_ARCH}

EXTRACT_ONLY=
WRKSRC=/usr/freenas_src

# no checksum, we just used git!
 #extract:
checksum fetch:
	echo ${.TARGET} not needed because building direct

pre-clean:
	@

ALL_TARGET=obj all

MAKE_JOBS_UNSAFE=yes

do-build:
	${MAKE} -C ${WRKSRC}/extract-tarball   obj
	${MAKE} -C ${WRKSRC}/extract-tarball  all
	${MAKE} -C ${WRKSRC}/winacl   obj
	${MAKE} -C ${WRKSRC}/winacl  all
	${MAKE} -C ${WRKSRC}/freenas-pkgtools obj
	${MAKE} -C ${WRKSRC}/freenas-pkgtools all

do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/boot
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/bin
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/etc
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/lib/freenasOS
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/libexec
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/sbin
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/libexec/samba
	${MAKE} -C ${WRKSRC}/extract-tarball  BINDIR=${STAGEDIR}${PREFIX}/usr/local/bin install
	${MAKE} -C ${WRKSRC}/winacl  BINDIR=${STAGEDIR}${PREFIX}/usr/local/bin install
	${MAKE} -C ${WRKSRC}/freenas-pkgtools BINDIR=${STAGEDIR}${PREFIX}/usr/local/bin LIBDIR=${STAGEDIR}${PREFIX}/usr/local/lib/freenasOS install
	#
	# Adding autotune
	#
	${INSTALL_SCRIPT} ${WRKSRC}/autotune/files/autotune.py ${STAGEDIR}${PREFIX}/usr/local/bin/autotune
	${INSTALL_SCRIPT} ${WRKSRC}/afpusers/files/afpusers.py ${STAGEDIR}${PREFIX}/usr/local/bin/afpusers
	#
	#
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/arc_summary.py ${STAGEDIR}/${PREFIX}/usr/local/bin/arc_summary.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/arcstat.py ${STAGEDIR}/${PREFIX}/usr/local/bin/arcstat.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/crashuploader ${STAGEDIR}/${PREFIX}/usr/local/bin/crashuploader
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/custom-upssched-cmd ${STAGEDIR}/${PREFIX}/usr/local/bin/custom-upssched-cmd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/freenas-debug ${STAGEDIR}/${PREFIX}/usr/local/bin/freenas-debug
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/ixdiagnose ${STAGEDIR}/${PREFIX}/usr/local/bin/ixdiagnose
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/mfistatus.py ${STAGEDIR}/${PREFIX}/usr/local/bin/mfistatus.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/perftests-nas ${STAGEDIR}/${PREFIX}/usr/local/bin/perftests-nas
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/zilstat ${STAGEDIR}/${PREFIX}/usr/local/bin/zilstat
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/adtool ${STAGEDIR}/${PREFIX}/usr/local/bin/adtool
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/etc/avahi
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/avahi/avahi-daemon.conf ${STAGEDIR}/${PREFIX}/usr/local/etc/avahi/avahi-daemon.conf
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/etc/nginx
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/etc/rc.d
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/samba.gdb ${STAGEDIR}/${PREFIX}/usr/local/etc/samba.gdb
	${INSTALL_DATA} ${WRKSRC}/freenas/usr/local/etc/sudoers ${STAGEDIR}/${PREFIX}/usr/local/etc/sudoers
	${INSTALL_DATA} ${WRKSRC}/freenas/usr/local/etc/appcafe.conf ${STAGEDIR}/${PREFIX}/usr/local/etc/appcafe.conf
	${INSTALL_DATA} ${WRKSRC}/freenas/usr/local/etc/warden.conf ${STAGEDIR}/${PREFIX}/usr/local/etc/warden.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/nginx/fastcgi_params ${STAGEDIR}/${PREFIX}/usr/local/etc/nginx/fastcgi_params
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/samba/samba-backtrace ${STAGEDIR}/${PREFIX}/usr/local/libexec/samba/samba-backtrace
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/sbin/sas2flash ${STAGEDIR}/${PREFIX}/usr/local/sbin/sas2flash
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/sbin/save_rrds.sh ${STAGEDIR}/${PREFIX}/usr/local/sbin/save_rrds.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/sbin/scrub ${STAGEDIR}/${PREFIX}/usr/local/sbin/scrub
	${MKDIR} ${STAGEDIR}${PREFIX}/usr/local/share/perftests-nas/tests
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/perftests-nas/tests/* ${STAGEDIR}${PREFIX}/usr/local/share/perftests-nas/tests/
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/www/data
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/rc.subr ${STAGEDIR}/${PREFIX}/etc/rc.subr
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/rc.d/cleanvar ${STAGEDIR}/${PREFIX}/etc/rc.d/cleanvar
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/rc.d/ix-bootstrap ${STAGEDIR}/${PREFIX}/etc/rc.d/ix-bootstrap
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/rc.d/ix-etc ${STAGEDIR}/${PREFIX}/etc/rc.d/ix-etc
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/rc.d/ix-network ${STAGEDIR}/${PREFIX}/etc/rc.d/ix-network

	${INSTALL_SCRIPT} ${WRKSRC}/freenas/boot/loader.conf ${STAGEDIR}${PREFIX}/boot/loader.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/csh.cshrc ${STAGEDIR}${PREFIX}/etc/csh.cshrc
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/devfs.rules ${STAGEDIR}${PREFIX}/etc/devfs.rules
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/exports ${STAGEDIR}${PREFIX}/etc/exports
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/freenas.conf ${STAGEDIR}${PREFIX}/etc/freenas.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/gettytab ${STAGEDIR}${PREFIX}/etc/gettytab
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ipfw.conf.block ${STAGEDIR}${PREFIX}/etc/ipfw.conf.block
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/netcli ${STAGEDIR}${PREFIX}/etc/netcli
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/netcli.sh ${STAGEDIR}${PREFIX}/etc/netcli.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/newsyslog.conf ${STAGEDIR}${PREFIX}/etc/newsyslog.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/pf.conf.block ${STAGEDIR}${PREFIX}/etc/pf.conf.block
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/pw.conf ${STAGEDIR}${PREFIX}/etc/pw.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/rc.conf ${STAGEDIR}${PREFIX}/etc/rc.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/sysctl.conf ${STAGEDIR}${PREFIX}/etc/sysctl.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/syslog.conf ${STAGEDIR}${PREFIX}/etc/syslog.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ttys ${STAGEDIR}${PREFIX}/etc/ttys
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/root/.bashrc ${STAGEDIR}${PREFIX}/.bashrc
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/root/.cshrc ${STAGEDIR}${PREFIX}/.cshrc
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/root/.profile ${STAGEDIR}${PREFIX}/.profile
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/root/.shrc ${STAGEDIR}${PREFIX}/.shrc

	mkdir -p ${STAGEDIR}/${PREFIX}/etc/directoryservice
	mkdir -p ${STAGEDIR}/${PREFIX}/etc/directoryservice/DomainController
	mkdir -p ${STAGEDIR}/${PREFIX}/etc/directoryservice/LDAP
	mkdir -p ${STAGEDIR}/${PREFIX}/etc/directoryservice/NIS
	mkdir -p ${STAGEDIR}/${PREFIX}/etc/directoryservice/NT4
	mkdir -p ${STAGEDIR}/${PREFIX}/etc/directoryservice/ActiveDirectory
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/directoryservice/ActiveDirectory/ctl ${STAGEDIR}/${PREFIX}/etc/directoryservice/ActiveDirectory/ctl
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/directoryservice/DomainController/ctl ${STAGEDIR}/${PREFIX}/etc/directoryservice/DomainController/ctl
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/directoryservice/LDAP/ctl ${STAGEDIR}/${PREFIX}/etc/directoryservice/LDAP/ctl
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/directoryservice/NIS/ctl ${STAGEDIR}/${PREFIX}/etc/directoryservice/NIS/ctl
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/directoryservice/NT4/ctl ${STAGEDIR}/${PREFIX}/etc/directoryservice/NT4/ctl
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/directoryservice/rc.ActiveDirectory ${STAGEDIR}/${PREFIX}/etc/directoryservice/rc.ActiveDirectory
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/directoryservice/rc.DomainController ${STAGEDIR}/${PREFIX}/etc/directoryservice/rc.DomainController
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/directoryservice/rc.LDAP ${STAGEDIR}/${PREFIX}/etc/directoryservice/rc.LDAP
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/directoryservice/rc.NIS ${STAGEDIR}/${PREFIX}/etc/directoryservice/rc.NIS
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/directoryservice/rc.NT4 ${STAGEDIR}/${PREFIX}/etc/directoryservice/rc.NT4
	mkdir -p ${STAGEDIR}/${PREFIX}/etc/ix
	mkdir -p ${STAGEDIR}/${PREFIX}/etc/ix/templates
	mkdir -p ${STAGEDIR}/${PREFIX}/etc/ix/templates/kerberos
	mkdir -p ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d
	mkdir -p ${STAGEDIR}/${PREFIX}/etc/ix/templates/warden
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/kerberos/krb5.conf ${STAGEDIR}/${PREFIX}/etc/ix/templates/kerberos/krb5.conf
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/README ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/README
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/atrun ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/atrun
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/cron ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/cron
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/ftp ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/ftp
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/ftpd ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/ftpd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/imap ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/imap
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/kde ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/kde
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/login ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/login
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/netatalk ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/netatalk
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/other ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/other
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/passwd ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/passwd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/pop3 ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/pop3
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/rsh ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/rsh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/samba ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/samba
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/sshd ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/sshd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/su ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/su
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/sudo ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/sudo
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/system ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/system
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/telnetd ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/telnetd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/pam.d/xdm ${STAGEDIR}/${PREFIX}/etc/ix/templates/pam.d/xdm
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/warden/jail-post-delete ${STAGEDIR}/${PREFIX}/etc/ix/templates/warden/jail-post-delete
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/warden/jail-post-start ${STAGEDIR}/${PREFIX}/etc/ix/templates/warden/jail-post-start
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/warden/jail-post-stop ${STAGEDIR}/${PREFIX}/etc/ix/templates/warden/jail-post-stop
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/warden/jail-pre-delete ${STAGEDIR}/${PREFIX}/etc/ix/templates/warden/jail-pre-delete
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/warden/jail-pre-start ${STAGEDIR}/${PREFIX}/etc/ix/templates/warden/jail-pre-start
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix/templates/warden/jail-pre-stop ${STAGEDIR}/${PREFIX}/etc/ix/templates/warden/jail-pre-stop
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/iso_3166_2_countries.csv ${STAGEDIR}/${PREFIX}/etc/iso_3166_2_countries.csv
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/find_alias_for_smtplib.py ${STAGEDIR}/${PREFIX}/etc/find_alias_for_smtplib.py

.include <bsd.port.mk>
