.if exists(build/hooks/Makefile)
.include "build/hooks/Makefile"
.endif

NANO_LABEL?=FreeNAS
VERSION?=9.2.1.10-RELEASE
BUILD_TIMESTAMP!=date '+%Y%m%d'
COMPANY?="iXsystems"

.ifdef SCRIPT
RELEASE_LOGFILE?=${SCRIPT}
.else
RELEASE_LOGFILE?=release.build.log
.endif

GIT_REPO_SETTING=${.CURDIR}/.git-repo-setting
.if exists(${GIT_REPO_SETTING})
GIT_LOCATION!=cat ${GIT_REPO_SETTING}
.endif
ENV_SETUP=env NANO_LABEL=${NANO_LABEL} VERSION=${VERSION} GIT_LOCATION=${GIT_LOCATION} BUILD_TIMESTAMP=${BUILD_TIMESTAMP}

all:	build

build: git-verify
	${ENV_SETUP} build/do_checkout.sh check-sandbox
	@[ `id -u` -eq 0 ] || (echo "Sorry, you must be running as root to build this."; exit 1)
	${ENV_SETUP} build/do_build.sh -z
	${ENV_SETUP} build/do_build.sh

checkout: git-verify
	${ENV_SETUP} build/do_checkout.sh

update: checkout

clean:
	${ENV_SETUP} build/build_cleanup.py
	rm -rf FreeBSD ${NANO_LABEL}-${VERSION}-* release.build.log nas_source

clean-packages:
	find os-base -name "*.tbz" -delete

distclean: clean

save-build-env:
	${ENV_SETUP} build/save_build.sh

freenas: release
release: git-verify
	${ENV_SETUP} build/do_checkout.sh check-sandbox
	@echo "Doing executing target $@ on host: `hostname`"
	@echo "Build directory: `pwd`"
	${ENV_SETUP} script -a ${RELEASE_LOGFILE} build/build_release.sh

rebuild:
	@${ENV_SETUP} ${MAKE} checkout
	@${ENV_SETUP} ${MAKE} all
	@${ENV_SETUP) sh build/create_release_distribution.sh

cdrom:
	${ENV_SETUP} sh -x build/create_iso.sh

truenas: git-verify
	@[ "${GIT_LOCATION}" = "INTERNAL" ] || (echo "You can only run this target from an internal repository."; exit 1)
	env NANO_LABEL=TrueNAS script -a ${RELEASE_LOGFILE} ${MAKE} build
	mkdir -p TrueNAS-${VERSION}-${BUILD_TIMESTAMP}
	mv os-base/amd64/TrueNAS-${VERSION}-* TrueNAS-${VERSION}-${BUILD_TIMESTAMP}

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

git-verify:
	@if [ ! -f ${GIT_REPO_SETTING} ]; then \
		echo "No git repo choice is set.  Please use \"make git-external\" to build as an"; \
		echo "external developer or \"make git-internal\" to build as an ${COMPANY}"; \
		echo "internal developer.  You only need to do this once."; \
		exit 1; \
	fi
	@echo "NOTICE: You are building from the ${GIT_LOCATION} git repo."

git-internal:
	@echo "INTERNAL" > ${GIT_REPO_SETTING}
	@echo "You are set up for internal (${COMPANY}) development.  You can use"
	@echo "the standard make targets (e.g. build or release) now."

git-external:
	@echo "EXTERNAL" > ${GIT_REPO_SETTING}
	@echo "You are set up for external (github) development.  You can use"
	@echo "the standard make targets (e.g. build or release) now."
