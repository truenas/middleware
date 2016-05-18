# Created by: Matt Peterson <matt@peterson.org>
# $FreeBSD: head/net-mgmt/collectd5/Makefile 414458 2016-05-02 16:08:56Z zeising $

PORTNAME=	collectd
PORTVERSION=	5.5.1
PORTREVISION=	5
CATEGORIES=	net-mgmt
MASTER_SITES=	https://collectd.org/files/ \
		http://collectd.org/files/
PKGNAMESUFFIX=	5

MAINTAINER=	ports@bsdserwis.com
COMMENT=	Systems & network statistics collection daemon

LICENSE=	GPLv2
LICENSE_FILE=	${WRKSRC}/COPYING

# Only autoreconf stage and sigrok plugin need GLIB:
BUILD_DEPENDS=	${LOCALBASE}/share/aclocal/glib-2.0.m4:devel/glib20
LIB_DEPENDS=	libltdl.so:devel/libltdl

USES=		autoreconf gmake libtool pkgconfig shebangfix tar:bzip2
GNU_CONFIGURE=	yes

OPTIONS_DEFINE=		CGI DEBUG GCRYPT LIBZFS LOGSTASH VIRT
OPTIONS_GROUP=		INPUT OUTPUT
OPTIONS_GROUP_OUTPUT=	KAFKA MONGODB NOTIFYDESKTOP NOTIFYEMAIL RIEMANN RRDTOOL \
			TSDB
OPTIONS_GROUP_INPUT=	CURL CURL_JSON CURL_XML DBI IPMI JSON MEMCACHEC \
			MODBUS MYSQL NUTUPS OLSRD ONEWIRE OPENLDAP \
			PERL PGSQL PINBA PING PYTHON RABBITMQ REDIS ROUTEROS \
			SIGROK SNMP STATSD TOKYOTYRANT VARNISH XML \
			XMMS ZOOKEEPER

CGI_DESC=		Install collection.cgi (requires rrdtool)
CURL_DESC=		Enable curl-based plugins (apache, nginx, etc)
CURL_JSON_DESC=		Enable curl_json plugin (implies curl and json)
CURL_XML_DESC=		Enable ascent, bind, curl_xml plugins (implies curl and xml)
DBI_DESC=		Enable dbi plugin
DEBUG_DESC=		Enable debugging
GCRYPT_DESC=		Build with libgcrypt
IPMI_DESC=		Enable OpenIPMI plugin
JSON_DESC=		Enable JSON plugins
KAFKA_DESC=		Enable write_kafka plugin
LIBZFS_DESC=	Build with LibZFS
LOGSTASH_DESC=		Enable log_logstash plugin (requires json)
MEMCACHEC_DESC=		Enable memcachec plugin
MODBUS_DESC=		Enable modbus plugin
MONGODB_DESC=		Enable write_mongodb plugin (BROKEN)
MYSQL_DESC=		Enable mysql-based plugins
NOTIFYDESKTOP_DESC=	Enable desktop notifications
NOTIFYEMAIL_DESC=	Enable notifications via email
NUTUPS_DESC=		Enable nut (ups) plugin
OLSRD_DESC=		Enable olsrd plugin
ONEWIRE_DESC=		Eanble onewire plugin (via owfs)
OPENLDAP_DESC=		Enable OpenLDAP plugin
PERL_DESC=		Enable libperl plugin and binding
PGSQL_DESC=		Enable postgresql-based plugins
PINBA_DESC=		Enable pinba plugin (via protobuf-c)
PING_DESC=		Enable ping plugin
PYTHON_DESC=		Enable python-based plugins
RABBITMQ_DESC=		Enable rabbitmq-based plugins
REDIS_DESC=		Enable redis-based plugins
RIEMANN_DESC=		Enable write_riemann plugin (via protobuf-c)
ROUTEROS_DESC=		Enable routeros plugin
RRDTOOL_DESC=		Enable rrdtool plugin (also rrdcached plugin)
SIGROK_DESC=		Enable sigrok plugin
SNMP_DESC=		Enable SNMP plugin
STATSD_DESC=		Enable statsd plugin
TOKYOTYRANT_DESC=	Enable tokyotyrant plugin
TSDB_DESC=		Enable write_tsdb plugin
VARNISH_DESC=		Enable varnish 4.x cache statistics
VIRT_DESC=		Enable libvirt plugin (requires XML)
XML_DESC=		Enable XML plugins
XMMS_DESC=		Enable xmms plugin
ZOOKEEPER_DESC=		Enable zookeeper plugin

OPTIONS_SUB=	yes

USE_RC_SUBR=	collectd collectdmon

USE_LDCONFIG=	yes

CPPFLAGS+=	-I${LOCALBASE}/include
LIBS+=		-L${LOCALBASE}/lib

# NOTE: Plugins without dependencies are defined further down.
CONFIGURE_ARGS=	--localstatedir=/var \
		--disable-all-plugins \
		--disable-static \
		--without-amqp \
		--disable-ceph \
		--disable-cgroups \
		--disable-fhcount \
		--without-java \
		--without-libaquaero5 \
		--without-libganglia \
		--without-libiptc \
		--without-libjvm \
		--without-liblvm2app \
		--without-libkstat \
		--without-libldap \
		--without-libmnl \
		--without-libnetlink \
		--without-libnetapp \
		--without-libowcapi \
		--without-libperfstat \
		--without-libsensors \
		--without-lvm \
		--without-mic \
		--without-oracle \
		--disable-turbostat

CGI_RUN_DEPENDS=		p5-URI>=0:net/p5-URI \
				p5-CGI>=0:www/p5-CGI \
				p5-Data-Dumper>=0:devel/p5-Data-Dumper \
				p5-HTML-Parser>=0:www/p5-HTML-Parser
CGI_IMPLIES=			RRDTOOL

CURL_LIB_DEPENDS=		libcurl.so:ftp/curl
CURL_CONFIGURE_ENABLE=		apache curl nginx write_http
CURL_CONFIGURE_WITH=		libcurl=${LOCALBASE}

CURL_JSON_IMPLIES=		CURL JSON
CURL_JSON_CONFIGURE_ENABLE=	curl_json

CURL_XML_IMPLIES=		CURL XML
CURL_XML_CONFIGURE_ENABLE=	ascent bind curl_xml

DEBUG_CONFIGURE_ENABLE=		debug

DBI_LIB_DEPENDS=		libdbi.so:databases/libdbi
DBI_CONFIGURE_WITH=		libdbi=${LOCALBASE}
DBI_CONFIGURE_ENABLE=		dbi
DBI_CFLAGS=			-Wno-deprecated-declarations

GCRYPT_LIB_DEPENDS=		libgcrypt.so:security/libgcrypt
GCRYPT_CONFIGURE_WITH=		-with-libgcrypt=${LOCALBASE}
GCRYPT_LIBS=			-lgcrypt

IPMI_LIB_DEPENDS=		libOpenIPMI.so:sysutils/openipmi
IPMI_CONFIGURE_ENABLE=		ipmi

JSON_LIB_DEPENDS=		libyajl.so:devel/yajl
JSON_CONFIGURE_WITH=		libyajl=${LOCALBASE}

KAFKA_LIB_DEPENDS=		librdkafka.so:net/librdkafka
KAFKA_CONFIGURE_ENABLE=		write_kafka

LOGSTASH_CONFIGURE_ENABLE=	log_logstash
LOGSTASH_IMPLIES=		JSON

MEMCACHEC_LIB_DEPENDS=		libmemcached.so:databases/libmemcached
MEMCACHEC_CONFIGURE_ENABLE=	memcachec
MEMCACHEC_CONFIGURE_WITH=	libmemcached=${LOCALBASE}

MODBUS_LIB_DEPENDS=		libmodbus.so:comms/libmodbus
MODBUS_CONFIGURE_ENABLE=	modbus
MODBUS_CONFIGURE_WITH=		libmodbus=use_pkgconfig

MONGODB_LIB_DEPENDS=		libmongoc-1.0.so:devel/mongo-c-driver
MONGODB_LIB_DEPENDS+=		libbson-1.0.so:devel/libbson
MONGODB_CONFIGURE_ENABLE=	write_mongodb
MONGODB_CONFIGURE_WITH=		libmongoc=${LOCALBASE}
MONGODB_BROKEN=			fails to configure with write_mongodb option

MYSQL_USE=			mysql=yes
MYSQL_CONFIGURE_ENABLE=		mysql
MYSQL_CONFIGURE_WITH=		libmysql=${LOCALBASE}

NOTIFYDESKTOP_LIB_DEPENDS=	libnotify.so:devel/libnotify
NOTIFYDESKTOP_CONFIGURE_ENABLE=	notify_desktop
NOTIFYDESKTOP_CONFIGURE_WITH=	libnotify=${LOCALBASE}

NOTIFYEMAIL_LIB_DEPENDS=	libesmtp.so:mail/libesmtp
NOTIFYEMAIL_CONFIGURE_ENABLE=	notify_email
NOTIFYEMAIL_CONFIGURE_WITH=	libesmtp=${LOCALBASE}

NUTUPS_LIB_DEPENDS=		libupsclient.so:sysutils/nut
NUTUPS_CONFIGURE_ENABLE=	nut
NUTUPS_CONFIGURE_WITH=		upsclient=${LOCALBASE}

OLSRD_CONFIGURE_ENABLE=		olsrd

ONEWIRE_LIB_DEPENDS=		libow.so:comms/owfs
ONEWIRE_CONFIGURE_ENABLE=	onewire
ONEWIRE_CONFIGURE_WITH=		libowcapi=${LOCALBASE}

OPENLDAP_USE=			openldap=yes
OPENLDAP_CONFIGURE_ENABLE=	openldap
OPENLDAP_CONFIGURE_WITH=	libldap=${LOCALBASE}

PERL_USES=			perl5
PERL_CONFIGURE_ENABLE=		perl
PERL_CONFIGURE_WITH=		perl=${PERL} perl-bindings

PGSQL_USES=			pgsql
PGSQL_CONFIGURE_ENABLE=		postgresql
PGSQL_CONFIGURE_WITH=		postgresql=${LOCALBASE} libpq

PINBA_LIB_DEPENDS=		libprotobuf-c.so:devel/protobuf-c
PINBA_CONFIGURE_ENABLE=		pinba

PING_LIB_DEPENDS=		liboping.so:net/liboping
PING_CONFIGURE_ENABLE=		ping
PING_CONFIGURE_WITH=		liboping=${LOCALBASE}

PYTHON_USES=			python:2
PYTHON_CONFIGURE_ENABLE=	python
PYTHON_CONFIGURE_WITH=		python=${PYTHON_CMD}

RABBITMQ_LIB_DEPENDS=		librabbitmq.so:net/rabbitmq-c
RABBITMQ_CONFIGURE_ENABLE=	rabbitmq
RABBITMQ_CONFIGURE_WITH=	librabbitmq=${LOCALBASE}

REDIS_LIB_DEPENDS=		libhiredis.so:databases/hiredis
REDIS_CONFIGURE_ENABLE=		redis write_redis
REDIS_CONFIGURE_WITH=		libhiredis=${LOCALBASE}

RIEMANN_LIB_DEPENDS=		libprotobuf-c.so:devel/protobuf-c
RIEMANN_CONFIGURE_ENABLE=	write_riemann

ROUTEROS_LIB_DEPENDS=		librouteros.so:net/librouteros
ROUTEROS_CONFIGURE_ENABLE=	routeros
ROUTEROS_CONFIGURE_WITH=	librouteros=${LOCALBASE}

RRDTOOL_LIB_DEPENDS=		librrd.so:databases/rrdtool
RRDTOOL_CONFIGURE_ENABLE=	rrdcached rrdtool
RRDTOOL_CONFIGURE_WITH=		librrd=${LOCALBASE}

SIGROK_USE=			GNOME=glib20
SIGROK_CFLAGS=			`pkg-config --cflags glib-2.0`
SIGROK_LIB_DEPENDS=		libsigrok.so:devel/libsigrok
SIGROK_CONFIGURE_ENABLE=	sigrok
SIGROK_CONFIGURE_WITH=		libsigrok

SNMP_LIB_DEPENDS=		libnetsnmp.so:net-mgmt/net-snmp
SNMP_CONFIGURE_ENABLE=		snmp
SNMP_CONFIGURE_WITH=		libnetsnmp

STATSD_CONFIGURE_ENABLE=	statsd

TOKYOTYRANT_LIB_DEPENDS=	libtokyotyrant.so:databases/tokyotyrant
TOKYOTYRANT_CONFIGURE_ENABLE=	tokyotyrant
TOKYOTYRANT_CONFIGURE_WITH=	libtokyotyrant=${LOCALBASE}

TSDB_CONFIGURE_ENABLE=		write_tsdb

VARNISH_LIB_DEPENDS=		libvarnishapi.so:www/varnish4
VARNISH_CONFIGURE_ENABLE=	varnish
VARNISH_CONFIGURE_WITH=		libvarnish=${LOCALBASE}

VIRT_IMPLIES=			XML
VIRT_LIB_DEPENDS=		libvirt.so:devel/libvirt
VIRT_CONFIGURE_ENABLE=		virt
VIRT_CONFIGURE_WITH=		virt=${LOCALBASE}

XML_LIB_DEPENDS=		libxml2.so:textproc/libxml2
XML_CONFIGURE_WITH=		libxml2=${LOCALBASE}

XMMS_CFLAGS=			`xmms-config --cflags`
XMMS_LIB_DEPENDS=		libxmms.so:multimedia/xmms
XMMS_CONFIGURE_ENABLE=		xmms
XMMS_CONFIGURE_WITH=		libxmms=${LOCALBASE}

ZOOKEEPER_LIB_DEPENDS=		libzookeeper_mt.so:devel/libzookeeper
ZOOKEEPER_CONFIGURE_ENABLE=	zookeeper
ZOOKEEPER_CONFIGURE_WITH=	libzookeeper=${LOCALBASE}

# NOTE: Plugins without external dependencies
CONFIGURE_ARGS+=--enable-aggregation \
		--enable-apcups \
		--enable-contextswitch \
		--enable-cpu \
		--enable-cputemp \
		--enable-csv \
		--enable-ctl \
		--enable-df \
		--enable-disk \
		--enable-dns \
		--enable-email \
		--enable-exec \
		--enable-filecount \
		--enable-geom-stat \
		--enable-interface \
		--enable-load \
		--enable-logfile \
		--enable-match_empty_counter \
		--enable-match_hashed \
		--enable-match_regex \
		--enable-match_timediff \
		--enable-match_value \
		--enable-mbmon \
		--enable-memcached \
		--enable-memory \
		--enable-network \
		--enable-ntpd \
		--enable-openvpn \
		--enable-powerdns \
		--enable-pf \
		--enable-processes \
		--enable-statsd \
		--enable-swap \
		--enable-syslog \
		--enable-table \
		--enable-tail \
		--enable-tail_csv \
		--enable-target_notification \
		--enable-target_replace \
		--enable-target_scale \
		--enable-target_set \
		--enable-target_v5upgrade \
		--enable-tcpconns \
		--enable-teamspeak2 \
		--enable-ted \
		--enable-threshold \
		--enable-unixsock \
		--enable-uptime \
		--enable-users \
		--enable-uuid \
		--enable-write_graphite \
		--enable-write_log \
		--enable-zfs_arc \
		--enable-zfs_arc_v2 \

INSTALL_TARGET=	install-strip
SHEBANG_FILES=	contrib/collection.cgi

.include <bsd.port.options.mk>

.if ${PORT_OPTIONS:MLIBZFS} && exists(/usr/lib/libzfs.so) && exists(/usr/lib/libzfs_core.so)
CONFIGURE_ARGS+=	--with-libzfs
.endif

post-patch:
	@${REINPLACE_CMD} 's/-Werror//' \
		${WRKSRC}/configure.ac ${WRKSRC}/src/Makefile.am \
		${WRKSRC}/src/libcollectdclient/Makefile.am
	@${REINPLACE_CMD} \
		-e 's;@prefix@/var/;/var/;' \
		-e 's;/var/lib/;/var/db/;' \
		-e 's;@localstatedir@/lib/;/var/db/;' \
		${WRKSRC}/src/collectd.conf.in \
		${WRKSRC}/src/collectd.conf.5
	@${REINPLACE_CMD} \
		-e 's;/etc/collection\.conf;${WWWDIR}/collection.conf;' \
		${WRKSRC}/contrib/collection.cgi
	@${REINPLACE_CMD} \
		-e 's;/opt/collectd/var/lib;/var/db;' \
		-e 's;/opt/collectd/lib;${PREFIX}/lib;' \
		${WRKSRC}/contrib/collection.conf

post-install:
	${MKDIR} ${STAGEDIR}/var/db/collectd

post-install-CGI-on:
	${MKDIR} ${STAGEDIR}${WWWDIR}
	${INSTALL_SCRIPT} ${WRKSRC}/contrib/collection.cgi ${STAGEDIR}${WWWDIR}/
	${INSTALL_DATA} ${WRKSRC}/contrib/collection.conf \
		${STAGEDIR}${WWWDIR}/collection.conf.sample

.include <bsd.port.mk>
