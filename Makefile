
NANO_LABEL?=FreeNAS
VERSION?=9.2.0-ALPHA

ENV_SETUP=env NANO_LABEL=${NANO_LABEL} VERSION=${VERSION} 

RELEASE_LOGFILE=release.build.log

all:
	[ `id -u` -eq 0 ] || (echo "Sorry, you must be running as root to build this."; exit 1)
	${ENV_SETUP} build/do_build.sh

checkout:
	${ENV_SETUP} build/do_build.sh -c

clean:
	${ENV_SETUP} build/build_cleanup.py

save-build-env:
	${ENV_SETUP} build/save_build.sh

release:
	${ENV_SETUP} script -a ${RELEASE_LOGFILE} ${MAKE} do-release

do-release:
	@echo "Doing executing target $@ on host: `hostname`"
	@echo "Build directory: `pwd`"
	${ENV_SETUP} build/build_release.sh

# Save the build environment
save-build-env:
	${ENV_SETUP} build/save_build.sh

cdrom:
	${ENV_SETUP} sh -x build/create_iso.sh

# Build truenas using all sources 
truenas-all-direct:
	${ENV_SETUP} TESTING_TRUENAS=1 NAS_PORTS_DIRECT=1 $(MAKE) all

# intentionally split up to prevent abuse/spam
BUILD_BUG_DOMAIN?=ixsystems.com
BUILD_BUG_USER?=build-bugs
BUILD_BUG_EMAIL?=${BUILD_BUG_USER}@${BUILD_BUG_DOMAIN}

build-bug-report:
	mail -s "build fail for $${SUDO_USER:-$$USER}" ${BUILD_BUG_EMAIL} < \
		${RELEASE_LOGFILE}
