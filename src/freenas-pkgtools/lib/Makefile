.include <bsd.own.mk>

LIBDIR=	${PREFIX}/lib/freenasOS
FILESDIR= ${LIBDIR}

FILES=	Configuration.py \
	Exceptions.py \
	Installer.py \
	Manifest.py \
	Package.py \
	Train.py \
	Update.py \
	PackageFile.py \
	__init__.py

beforeinstall:
	${INSTALL} -d ${DESTDIR}${LIBDIR}

.include <bsd.lib.mk>

