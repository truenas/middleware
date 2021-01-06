PORTNAME=	middlewared
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}
PKGNAMEPREFIX=  ${PYTHON_PKGNAMEPREFIX}

CATEGORIES=     freenas
VALID_CATEGORIES+= freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        FreeNAS Middleware Daemon

USES=		python
USE_PYTHON=	autoplist distutils
EXTRACT_ONLY=

BUILD_DEPENDS= ${PYTHON_PKGNAMEPREFIX}fastentrypoints>0:devel/py-fastentrypoints@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}Babel>0:devel/py-babel@${PY_FLAVOR}
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}ws4py>0:www/py-ws4py@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}aiohttp>0:www/py-aiohttp@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}aiohttp-wsgi>0:www/py-aiohttp-wsgi@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}Flask>0:www/py-flask@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}boto3>0:www/py-boto3@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}netif>0:net/py-netif@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}bsd>0:freenas/py-bsd@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}cam>0:devel/py-cam@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}sentry-sdk>0:devel/py-sentry-sdk@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}markdown>0:textproc/py-markdown@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}mako>0:textproc/py-mako@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}psutil>0:sysutils/py-psutil@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}ldap>0:net/py-ldap@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}libzfs>0:devel/py-libzfs@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}lockfile>0:devel/py-lockfile@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}netsnmpagent>0:net/py-netsnmpagent@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}ntplib>0:net/py-ntplib@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}pydevd>0:devel/py-pydevd@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}pysnmp>0:net-mgmt/py-pysnmp@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}remote-pdb>0:devel/py-remote-pdb@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}requests>0:www/py-requests@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}requests-toolbelt>0:www/py-requests-toolbelt@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}zeroconf>0:net/py-zeroconf@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}influxdb>0:databases/py-influxdb@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}asyncssh>0:security/py-asyncssh@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}croniter>0:sysutils/py-croniter@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}aiorwlock>0:devel/py-aiorwlock@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}bidict>0:devel/py-bidict@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}markdown2>0:textproc/py-markdown2@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}acme>0:security/py-acme@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}josepy>0:security/py-josepy@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}certbot-dns-cloudflare>0:security/py-certbot-dns-cloudflare@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}certbot-dns-digitalocean>0:security/py-certbot-dns-digitalocean@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}certbot-dns-google>0:security/py-certbot-dns-google@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}certbot-dns-ovh>0:security/py-certbot-dns-ovh@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}pyotp>0:security/py-pyotp@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}libvirt>0:devel/py-libvirt@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}zettarepl>0:sysutils/py-zettarepl@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}onedrivesdk>0:devel/py-onedrivesdk@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}fenced>0:truenas/py-fenced@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}alembic>0:databases/py-alembic@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}sqlalchemy13>0:databases/py-sqlalchemy13@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}licenselib>0:freenas/py-licenselib@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}simplejson>0:devel/py-simplejson@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}sqlparse>0:databases/py-sqlparse@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}pycryptodome>0:security/py-pycryptodome@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}openssl>0:security/py-openssl@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}dnspython>0:dns/py-dnspython@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}lxml>0:devel/py-lxml@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}sysctl>0:devel/py-sysctl@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}ipaddr>0:devel/py-ipaddr@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}setproctitle>0:devel/py-setproctitle@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}kmip>0:devel/py-kmip@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}google-api-python-client>0:www/py-google-api-python-client@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}google-auth>0:security/py-google-auth@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}passlib>0:security/py-passlib@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}html2text>0:textproc/py-html2text@${PY_FLAVOR} \
		freenas-pkgtools>0:freenas/freenas-pkgtools \
		freenas-migrate93>0:freenas/freenas-migrate93 \
		freenas-migrate113>0:freenas/freenas-migrate113 \
		tc-stats>0:freenas/tc-stats \
		${PYTHON_PKGNAMEPREFIX}iocage>0:sysutils/iocage@${PY_FLAVOR} \
		git-lite>0:devel/git-lite \
		oath-toolkit>0:security/oath-toolkit \
		avahi-app>0:net/avahi-app \
		dmidecode>0:sysutils/dmidecode \
		grub2>0:sysutils/grub2 \
		grub2-x86_64-efi>0:sysutils/grub2-x86_64-efi \
		squashfs-tools>0:sysutils/squashfs-tools \
		${PYTHON_PKGNAMEPREFIX}packaging>0:devel/py-packaging@${PY_FLAVOR} \
		rclone>0:net/rclone \
		ifstat>0:net/ifstat \
		iftop>0:net-mgmt/iftop \
		intel-pcm>0:sysutils/intel-pcm \
		pyvmomi>0:net/py-pyvmomi \
		samba>=0:net/samba \
		swagger-ui>0:freenas/swagger-ui \
		wireguard>0:net/wireguard

USE_RC_SUBR=	middlewared

WRKSRC?=/usr/nas_source/middlewared

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
