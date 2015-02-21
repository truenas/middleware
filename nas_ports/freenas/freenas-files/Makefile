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
WRKSRC=/usr/nas_source2

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
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/bin
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/bin/freenas-snmp
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/etc
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/lib/freenasOS
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/libexec
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/sbin
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
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/fixsid.py ${STAGEDIR}/${PREFIX}/usr/local/bin/fixsid.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/freenas-debug ${STAGEDIR}/${PREFIX}/usr/local/bin/freenas-debug
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/ixdiagnose ${STAGEDIR}/${PREFIX}/usr/local/bin/ixdiagnose
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/mfistatus.py ${STAGEDIR}/${PREFIX}/usr/local/bin/mfistatus.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/perftests-nas ${STAGEDIR}/${PREFIX}/usr/local/bin/perftests-nas
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/sas2ircu ${STAGEDIR}/${PREFIX}/usr/local/bin/sas2ircu
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/zilstat ${STAGEDIR}/${PREFIX}/usr/local/bin/zilstat
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/adtool ${STAGEDIR}/${PREFIX}/usr/local/bin/adtool
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/ldaptool ${STAGEDIR}/${PREFIX}/usr/local/bin/ldaptool
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/chelsio_adapter_config ${STAGEDIR}/${PREFIX}/usr/local/bin/chelsio_adapter_config
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/t5seeprom ${STAGEDIR}/${PREFIX}/usr/local/bin/t5seeprom
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/sockscopy ${STAGEDIR}/${PREFIX}/usr/local/bin/sockscopy
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/freenas-snmp/__init__.py ${STAGEDIR}/${PREFIX}/usr/local/bin/freenas-snmp/__init__.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/freenas-snmp/snmpresponse.py ${STAGEDIR}/${PREFIX}/usr/local/bin/freenas-snmp/snmpresponse.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/bin/freenas-snmp/zfs-snmp ${STAGEDIR}/${PREFIX}/usr/local/bin/freenas-snmp/zfs-snmp
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/etc/avahi
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/avahi/avahi-daemon.conf ${STAGEDIR}/${PREFIX}/usr/local/etc/avahi/avahi-daemon.conf
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/etc/default
	${INSTALL_DATA} ${WRKSRC}/freenas/usr/local/etc/default/grub ${STAGEDIR}/${PREFIX}/usr/local/etc/default/grub
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/etc/nginx
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/nginx/fastcgi_params ${STAGEDIR}/${PREFIX}/usr/local/etc/nginx/fastcgi_params
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/nginx/nginx.conf ${STAGEDIR}/${PREFIX}/usr/local/etc/nginx/nginx.conf
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/etc/rc.d
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/rc.d/django ${STAGEDIR}/${PREFIX}/usr/local/etc/rc.d/django
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/rc.d/ldpbiconfig ${STAGEDIR}/${PREFIX}/usr/local/etc/rc.d/ldpbiconfig
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/rc.d/pbid ${STAGEDIR}/${PREFIX}/usr/local/etc/rc.d/pbid
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/samba.gdb ${STAGEDIR}/${PREFIX}/usr/local/etc/samba.gdb
	${INSTALL_DATA} ${WRKSRC}/freenas/usr/local/etc/sudoers ${STAGEDIR}/${PREFIX}/usr/local/etc/sudoers
	${INSTALL_DATA} ${WRKSRC}/freenas/usr/local/etc/syslog-ng.conf.freenas ${STAGEDIR}/${PREFIX}/usr/local/etc/syslog-ng.conf.freenas
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/active_directory
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/cache
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/domain_controller
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/dtrace
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/geom
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/hardware
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/ipmi
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/iscsi
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/ldap
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/loader
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/network
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/nfs
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/smart
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/ssl
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/sysctl
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/system
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/verify
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/zfs
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/etc/nginx/fastcgi_params ${STAGEDIR}/${PREFIX}/usr/local/etc/nginx/fastcgi_params
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/active_directory/active_directory.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/active_directory/active_directory.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/cache/cache.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/cache/cache.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/domain_controller/domain_controller.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/domain_controller/domain_controller.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/dtrace/* ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/dtrace/
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/geom/geom.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/geom/geom.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/hardware/hardware.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/hardware/hardware.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/include.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/include.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/ipmi/ipmi.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/ipmi/ipmi.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/iscsi/iscsi.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/iscsi/iscsi.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/ldap/ldap.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/ldap/ldap.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/loader/loader.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/loader/loader.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/network/network.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/network/network.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/nfs/nfs.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/nfs/nfs.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/smart/smart.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/smart/smart.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/ssl/ssl.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/ssl/ssl.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/sysctl/sysctl.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/sysctl/sysctl.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/system/system.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/system/system.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/zfs/zfs.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/zfs/zfs.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/freenas-debug/verify/verify.sh ${STAGEDIR}/${PREFIX}/usr/local/libexec/freenas-debug/verify/verify.sh
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/nas
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/nas/generate_afpd_conf.py ${STAGEDIR}/${PREFIX}/usr/local/libexec/nas/generate_afpd_conf.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/nas/generate_ctl_conf.py ${STAGEDIR}/${PREFIX}/usr/local/libexec/nas/generate_ctl_conf.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/nas/generate_krb5_conf.py ${STAGEDIR}/${PREFIX}/usr/local/libexec/nas/generate_krb5_conf.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/nas/generate_ldap_conf.py ${STAGEDIR}/${PREFIX}/usr/local/libexec/nas/generate_ldap_conf.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/nas/generate_nsswitch_conf.py ${STAGEDIR}/${PREFIX}/usr/local/libexec/nas/generate_nsswitch_conf.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/nas/generate_resolv_conf.py ${STAGEDIR}/${PREFIX}/usr/local/libexec/nas/generate_resolv_conf.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/nas/generate_smb4_conf.py ${STAGEDIR}/${PREFIX}/usr/local/libexec/nas/generate_smb4_conf.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/nas/generate_ssl_certificates.py ${STAGEDIR}/${PREFIX}/usr/local/libexec/nas/generate_ssl_certificates.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/nas/generate_sssd_conf.py ${STAGEDIR}/${PREFIX}/usr/local/libexec/nas/generate_sssd_conf.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/nas/generate_webdav_conf.py ${STAGEDIR}/${PREFIX}/usr/local/libexec/nas/generate_webdav_conf.py
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/nas/register_mdns.py ${STAGEDIR}/${PREFIX}/usr/local/libexec/nas/register_mdns.py
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/libexec/samba
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/libexec/samba/samba-backtrace ${STAGEDIR}/${PREFIX}/usr/local/libexec/samba/samba-backtrace
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/sbin/sas2flash ${STAGEDIR}/${PREFIX}/usr/local/sbin/sas2flash
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/sbin/save_rrds.sh ${STAGEDIR}/${PREFIX}/usr/local/sbin/save_rrds.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/sbin/scrub ${STAGEDIR}/${PREFIX}/usr/local/sbin/scrub
	${MKDIR} ${STAGEDIR}${PREFIX}/usr/local/share/perftests-nas/tests
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/perftests-nas/tests/* ${STAGEDIR}${PREFIX}/usr/local/share/perftests-nas/tests/
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/www/data
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/www/data/django.fcgi ${STAGEDIR}/${PREFIX}/usr/local/www/data/django.fcgi
	mkdir -p ${STAGEDIR}/${PREFIX}/etc/ix.rc.d
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-activedirectory ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-activedirectory
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-afpd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-afpd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-aliases ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-aliases
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-ataidle ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-ataidle
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-snmpd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-snmpd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-cache ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-cache
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-collectd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-collectd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-crontab ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-crontab
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-ctld ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-ctld
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-device_hints ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-device_hints
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-fstab ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-fstab
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-hostname ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-hostname
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-inadyn ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-inadyn
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-inetd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-inetd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-jail ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-jail
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-kerberos ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-kerberos
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-kinit ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-kinit
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-ldap ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-ldap
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-loader ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-loader
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-localtime ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-localtime
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-motd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-motd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-multipath ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-multipath
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-nfsd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-nfsd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-nginx ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-nginx
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-nis ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-nis
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-nsswitch ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-nsswitch
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-nt4 ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-nt4
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-ntpd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-ntpd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-pam ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-pam
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-passwd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-passwd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-plugins ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-plugins
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-postinit ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-postinit
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-preinit ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-preinit
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-proftpd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-proftpd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-resolv ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-resolv
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-rsyncd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-rsyncd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-pre-samba ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-pre-samba
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-post-samba ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-post-samba
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-savehostid ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-savehostid
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-shutdown ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-shutdown
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-smartd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-smartd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-smbpasswd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-smbpasswd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-sshd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-sshd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-ssl ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-ssl
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-sssd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-sssd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-swap ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-swap
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-sudoers ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-sudoers
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-syncdisks ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-syncdisks
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-sysctl ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-sysctl
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-syslogd ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-syslogd
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-system ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-system
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-ttys ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-ttys
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-update ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-update
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-ups ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-ups
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-warden ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-warden
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-zfs ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-zfs
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix_diagnose ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix_diagnose
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix_pf_early ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix_pf_early
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix_pf_late ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix_pf_late
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix_register ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix_register
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix_sshd_save_keys ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix_sshd_save_keys
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix_textdump ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix_textdump
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/ix.rc.d/ix-apache ${STAGEDIR}/${PREFIX}/etc/ix.rc.d/ix-apache

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
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/iso_3166_2_countries.csv ${STAGEDIR}/${PREFIX}/etc/iso_3166_2_countries.csv
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/netcli ${STAGEDIR}/${PREFIX}/etc/netcli
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/netcli.sh ${STAGEDIR}/${PREFIX}/etc/netcli.sh
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/etc/find_alias_for_smtplib.py ${STAGEDIR}/${PREFIX}/etc/find_alias_for_smtplib.py
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/share/firmware
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/share/vpds
	mkdir -p ${STAGEDIR}/${PREFIX}/usr/local/share/snmp/mibs
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/firmware/t5fw-1.12.25.0.bin ${STAGEDIR}/${PREFIX}/usr/local/share/firmware/t5fw-1.12.25.0.bin
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/vpds/t580_cr_qsa_variable_2133_vpd.bin ${STAGEDIR}/${PREFIX}/usr/local/share/vpds/t580_cr_qsa_variable_2133_vpd.bin
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/vpds/t580_cr_spider_variable_2133_vpd.bin ${STAGEDIR}/${PREFIX}/usr/local/share/vpds/t580_cr_spider_variable_2133_vpd.bin
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/vpds/t580_cr_variable_2133_vpd.bin ${STAGEDIR}/${PREFIX}/usr/local/share/vpds/t580_cr_variable_2133_vpd.bin
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/vpds/t580_lp_cr_qsa_variable_2133_vpd.bin ${STAGEDIR}/${PREFIX}/usr/local/share/vpds/t580_lp_cr_qsa_variable_2133_vpd.bin
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/vpds/t580_lp_cr_spider_variable_2133_vpd.bin ${STAGEDIR}/${PREFIX}/usr/local/share/vpds/t580_lp_cr_spider_variable_2133_vpd.bin
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/vpds/t580_lp_cr_variable_2133_vpd.bin ${STAGEDIR}/${PREFIX}/usr/local/share/vpds/t580_lp_cr_variable_2133_vpd.bin
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/vpds/t580_lp_so_qsa_variable_vpd.bin ${STAGEDIR}/${PREFIX}/usr/local/share/vpds/t580_lp_so_qsa_variable_vpd.bin
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/vpds/t580_lp_so_spider_variable_2133_vpd.bin ${STAGEDIR}/${PREFIX}/usr/local/share/vpds/t580_lp_so_spider_variable_2133_vpd.bin
	${INSTALL_SCRIPT} ${WRKSRC}/freenas/usr/local/share/vpds/t580_lp_so_variable_vpd.bin ${STAGEDIR}/${PREFIX}/usr/local/share/vpds/t580_lp_so_variable_vpd.bin
	${INSTALL_DATA} ${WRKSRC}/freenas/usr/local/share/snmp/mibs/FREENAS-MIB.txt ${STAGEDIR}/${PREFIX}/usr/local/share/snmp/mibs/FREENAS-MIB.txt
.include <bsd.port.mk>
